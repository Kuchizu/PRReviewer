from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from random import choice
from app.database import get_db, init_db
from app.models import User, Team, PullRequest
from app.schemas import (
    TeamCreate, TeamResponse, TeamMember,
    SetActiveRequest, User as UserSchema,
    CreatePRRequest, MergePRRequest, ReassignRequest,
    PullRequest as PRSchema, PullRequestShort,
    ErrorResponse, ErrorDetail,
    GetReviewResponse, ReassignResponse
)

app = FastAPI(title='PR Reviewer Assignment Service', version='1.0.0')


@app.on_event('startup')
def startup():
    init_db()


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/team/add', status_code=201, response_model=dict)
def add_team(team_data: TeamCreate, db: Session = Depends(get_db)):
    existing = db.query(Team).filter(Team.name == team_data.team_name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail={'error': {'code': 'TEAM_EXISTS', 'message': 'team_name already exists'}}
        )

    team = Team(id=team_data.team_name, name=team_data.team_name)

    for member in team_data.members:
        user = db.query(User).filter(User.id == member.user_id).first()
        if user:
            user.username = member.username
            user.is_active = member.is_active
            user.team_id = team.id
        else:
            user = User(
                id=member.user_id,
                username=member.username,
                is_active=member.is_active,
                team_id=team.id
            )
            db.add(user)

    db.add(team)
    db.commit()
    db.refresh(team)

    members = [TeamMember(user_id=u.id, username=u.username, is_active=u.is_active) for u in team.members]
    return {'team': TeamResponse(team_name=team.name, members=members)}


@app.get('/team/get', response_model=TeamResponse)
def get_team(team_name: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.name == team_name).first()
    if not team:
        raise HTTPException(
            status_code=404,
            detail={'error': {'code': 'NOT_FOUND', 'message': 'team not found'}}
        )

    members = [TeamMember(user_id=u.id, username=u.username, is_active=u.is_active) for u in team.members]
    return TeamResponse(team_name=team.name, members=members)


@app.post('/users/setIsActive', response_model=dict)
def set_user_active(req: SetActiveRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={'error': {'code': 'NOT_FOUND', 'message': 'user not found'}}
        )

    user.is_active = req.is_active
    db.commit()
    db.refresh(user)

    team = db.query(Team).filter(Team.id == user.team_id).first()
    team_name = team.name if team else None

    return {
        'user': UserSchema(
            user_id=user.id,
            username=user.username,
            team_name=team_name,
            is_active=user.is_active
        )
    }


def get_active_reviewers(db: Session, team_id: str, exclude_user_id: str):
    return db.query(User).filter(
        User.team_id == team_id,
        User.is_active == True,
        User.id != exclude_user_id
    ).all()


@app.post('/pullRequest/create', status_code=201, response_model=dict)
def create_pr(req: CreatePRRequest, db: Session = Depends(get_db)):
    pr_exists = db.query(PullRequest).filter(PullRequest.id == req.pull_request_id).first()
    if pr_exists:
        raise HTTPException(
            status_code=409,
            detail={'error': {'code': 'PR_EXISTS', 'message': 'PR id already exists'}}
        )

    author = db.query(User).filter(User.id == req.author_id).first()
    if not author:
        raise HTTPException(
            status_code=404,
            detail={'error': {'code': 'NOT_FOUND', 'message': 'author not found'}}
        )

    team = db.query(Team).filter(Team.id == author.team_id).first()
    if not team:
        raise HTTPException(
            status_code=404,
            detail={'error': {'code': 'NOT_FOUND', 'message': 'team not found'}}
        )

    reviewers = get_active_reviewers(db, team.id, req.author_id)
    selected_reviewers = []
    if len(reviewers) >= 2:
        import random
        selected_reviewers = random.sample(reviewers, 2)
    elif len(reviewers) == 1:
        selected_reviewers = [reviewers[0]]

    pr = PullRequest(
        id=req.pull_request_id,
        name=req.pull_request_name,
        author_id=req.author_id,
        status='OPEN',
        assigned_reviewers=selected_reviewers
    )

    db.add(pr)
    db.commit()
    db.refresh(pr)

    return {
        'pr': PRSchema(
            pull_request_id=pr.id,
            pull_request_name=pr.name,
            author_id=pr.author_id,
            status=pr.status,
            assigned_reviewers=[r.id for r in pr.assigned_reviewers],
            createdAt=pr.created_at,
            mergedAt=pr.merged_at
        )
    }


@app.post('/pullRequest/merge', response_model=dict)
def merge_pr(req: MergePRRequest, db: Session = Depends(get_db)):
    pr = db.query(PullRequest).filter(PullRequest.id == req.pull_request_id).first()
    if not pr:
        raise HTTPException(
            status_code=404,
            detail={'error': {'code': 'NOT_FOUND', 'message': 'PR not found'}}
        )

    if pr.status != 'MERGED':
        pr.status = 'MERGED'
        pr.merged_at = datetime.utcnow()
        db.commit()

    db.refresh(pr)

    return {
        'pr': PRSchema(
            pull_request_id=pr.id,
            pull_request_name=pr.name,
            author_id=pr.author_id,
            status=pr.status,
            assigned_reviewers=[r.id for r in pr.assigned_reviewers],
            createdAt=pr.created_at,
            mergedAt=pr.merged_at
        )
    }


@app.post('/pullRequest/reassign', response_model=ReassignResponse)
def reassign_pr(req: ReassignRequest, db: Session = Depends(get_db)):
    pr = db.query(PullRequest).filter(PullRequest.id == req.pull_request_id).first()
    if not pr:
        raise HTTPException(
            status_code=404,
            detail={'error': {'code': 'NOT_FOUND', 'message': 'PR not found'}}
        )

    if pr.status == 'MERGED':
        raise HTTPException(
            status_code=409,
            detail={'error': {'code': 'PR_MERGED', 'message': 'cannot reassign on merged PR'}}
        )

    old_reviewer = db.query(User).filter(User.id == req.old_user_id).first()
    if not old_reviewer or old_reviewer not in pr.assigned_reviewers:
        raise HTTPException(
            status_code=409,
            detail={'error': {'code': 'NOT_ASSIGNED', 'message': 'reviewer is not assigned to this PR'}}
        )

    candidates = get_active_reviewers(db, old_reviewer.team_id, req.old_user_id)
    candidates = [c for c in candidates if c not in pr.assigned_reviewers and c.id != pr.author_id]

    if not candidates:
        raise HTTPException(
            status_code=409,
            detail={'error': {'code': 'NO_CANDIDATE', 'message': 'no active replacement candidate in team'}}
        )

    new_reviewer = choice(candidates)

    pr.assigned_reviewers.remove(old_reviewer)
    pr.assigned_reviewers.append(new_reviewer)

    db.commit()
    db.refresh(pr)

    return ReassignResponse(
        pr=PRSchema(
            pull_request_id=pr.id,
            pull_request_name=pr.name,
            author_id=pr.author_id,
            status=pr.status,
            assigned_reviewers=[r.id for r in pr.assigned_reviewers],
            createdAt=pr.created_at,
            mergedAt=pr.merged_at
        ),
        replaced_by=new_reviewer.id
    )


@app.get('/users/getReview', response_model=GetReviewResponse)
def get_review(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={'error': {'code': 'NOT_FOUND', 'message': 'user not found'}}
        )

    prs = [
        PullRequestShort(
            pull_request_id=pr.id,
            pull_request_name=pr.name,
            author_id=pr.author_id,
            status=pr.status
        )
        for pr in user.assigned_prs
    ]

    return GetReviewResponse(user_id=user.id, pull_requests=prs)


@app.get('/stats')
def get_stats(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    total_teams = db.query(Team).count()
    total_prs = db.query(PullRequest).count()
    open_prs = db.query(PullRequest).filter(PullRequest.status == 'OPEN').count()
    merged_prs = db.query(PullRequest).filter(PullRequest.status == 'MERGED').count()

    user_assignments = db.query(
        User.id,
        func.count(PullRequest.id).label('assignment_count')
    ).join(PullRequest.assigned_reviewers, isouter=True).group_by(User.id).all()

    return {
        'total_users': total_users,
        'total_teams': total_teams,
        'total_prs': total_prs,
        'open_prs': open_prs,
        'merged_prs': merged_prs,
        'user_assignments': [
            {'user_id': user_id, 'assignment_count': count or 0}
            for user_id, count in user_assignments
        ]
    }

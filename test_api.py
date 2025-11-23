import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app, get_db
from app.models import Base

SQLALCHEMY_DATABASE_URL = 'sqlite:///./test.db'

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={'check_same_thread': False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_create_team():
    response = client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True}
        ]
    })
    assert response.status_code == 201
    data = response.json()
    assert data['team']['team_name'] == 'backend'
    assert len(data['team']['members']) == 2


def test_create_duplicate_team():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [{'user_id': 'u1', 'username': 'Alice', 'is_active': True}]
    })
    response = client.post('/team/add', json={
        'team_name': 'backend',
        'members': [{'user_id': 'u2', 'username': 'Bob', 'is_active': True}]
    })
    assert response.status_code == 400
    assert response.json()['detail']['error']['code'] == 'TEAM_EXISTS'


def test_get_team():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True}
        ]
    })
    response = client.get('/team/get?team_name=backend')
    assert response.status_code == 200
    data = response.json()
    assert data['team_name'] == 'backend'
    assert len(data['members']) == 2


def test_get_nonexistent_team():
    response = client.get('/team/get?team_name=nonexistent')
    assert response.status_code == 404
    assert response.json()['detail']['error']['code'] == 'NOT_FOUND'


def test_set_user_active():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [{'user_id': 'u1', 'username': 'Alice', 'is_active': True}]
    })
    response = client.post('/users/setIsActive', json={'user_id': 'u1', 'is_active': False})
    assert response.status_code == 200
    data = response.json()
    assert data['user']['is_active'] is False


def test_set_nonexistent_user_active():
    response = client.post('/users/setIsActive', json={'user_id': 'u999', 'is_active': False})
    assert response.status_code == 404
    assert response.json()['detail']['error']['code'] == 'NOT_FOUND'


def test_create_pr():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True},
            {'user_id': 'u3', 'username': 'Charlie', 'is_active': True}
        ]
    })
    response = client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    assert response.status_code == 201
    data = response.json()
    assert data['pr']['pull_request_id'] == 'pr-1'
    assert data['pr']['status'] == 'OPEN'
    assert len(data['pr']['assigned_reviewers']) == 2


def test_create_duplicate_pr():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [{'user_id': 'u1', 'username': 'Alice', 'is_active': True}]
    })
    client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    response = client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    assert response.status_code == 409
    assert response.json()['detail']['error']['code'] == 'PR_EXISTS'


def test_merge_pr():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True}
        ]
    })
    client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    response = client.post('/pullRequest/merge', json={'pull_request_id': 'pr-1'})
    assert response.status_code == 200
    data = response.json()
    assert data['pr']['status'] == 'MERGED'
    assert data['pr']['mergedAt'] is not None




def test_reassign_merged_pr():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True}
        ]
    })
    client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    client.post('/pullRequest/merge', json={'pull_request_id': 'pr-1'})
    response = client.post('/pullRequest/reassign', json={
        'pull_request_id': 'pr-1',
        'old_user_id': 'u2'
    })
    assert response.status_code == 409
    assert response.json()['detail']['error']['code'] == 'PR_MERGED'


def test_get_review():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True}
        ]
    })
    client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    response = client.get('/users/getReview?user_id=u2')
    assert response.status_code == 200
    data = response.json()
    assert data['user_id'] == 'u2'
    assert len(data['pull_requests']) >= 1


def test_merge_pr_idempotent():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True}
        ]
    })
    client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })

    response1 = client.post('/pullRequest/merge', json={'pull_request_id': 'pr-1'})
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1['pr']['status'] == 'MERGED'
    merged_at_1 = data1['pr']['mergedAt']

    response2 = client.post('/pullRequest/merge', json={'pull_request_id': 'pr-1'})
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2['pr']['status'] == 'MERGED'
    assert data2['pr']['mergedAt'] == merged_at_1


def test_create_pr_with_one_active():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True}
        ]
    })
    response = client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    assert response.status_code == 201
    data = response.json()
    assert len(data['pr']['assigned_reviewers']) == 1
    assert 'u2' in data['pr']['assigned_reviewers']


def test_create_pr_no_active_reviewers():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': False}
        ]
    })
    response = client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    assert response.status_code == 201
    data = response.json()
    assert len(data['pr']['assigned_reviewers']) == 0




def test_get_review_nonexistent_user():
    response = client.get('/users/getReview?user_id=u999')
    assert response.status_code == 404
    assert response.json()['detail']['error']['code'] == 'NOT_FOUND'


def test_author_not_reviewer():
    client.post('/team/add', json={
        'team_name': 'backend',
        'members': [
            {'user_id': 'u1', 'username': 'Alice', 'is_active': True},
            {'user_id': 'u2', 'username': 'Bob', 'is_active': True},
            {'user_id': 'u3', 'username': 'Charlie', 'is_active': True}
        ]
    })
    response = client.post('/pullRequest/create', json={
        'pull_request_id': 'pr-1',
        'pull_request_name': 'Add feature',
        'author_id': 'u1'
    })
    assert response.status_code == 201
    data = response.json()
    assert 'u1' not in data['pr']['assigned_reviewers']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

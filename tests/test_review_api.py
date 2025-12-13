# tests/test_review_api.py
import pytest
from unittest.mock import Mock

# We will be testing the endpoints located in the review router
from app.api import review

def test_start_review_preparation(authenticated_client, mocker):
    """
    Tests that the endpoint to start the clustering process works correctly.
    """
    # Mock the actual function that runs in the background to avoid running a slow process
    mock_prepare = mocker.patch('app.api.review.prepare_review_session', return_value="Clustering complete.")
    
    response = authenticated_client.post("/api/review/prepare")
    
    assert response.status_code == 200
    assert "process has been started" in response.json()["message"]
    # We can't directly check if the background task ran, but this confirms the endpoint works.

def test_get_review_clusters(authenticated_client, mocker):
    """
    Tests fetching the list of generated clusters.
    """
    # Create some fake cluster data that the API should return
    fake_clusters = [
        {"cluster_id": "cluster_1", "name": "ssh-failed-logins", "log_count": 50},
        {"cluster_id": "cluster_2", "name": "kernel-panics", "log_count": 5}
    ]
    # Mock the function that gets data from the database
    mocker.patch('app.api.review.run_in_threadpool', return_value=fake_clusters)

    response = authenticated_client.get("/api/review/clusters")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "ssh-failed-logins"

def test_label_cluster(authenticated_client, mocker):
    """
    Tests the endpoint for applying a label to an entire cluster.
    """
    # Mock the database update function
    mock_update_db = mocker.patch('app.api.review.run_in_threadpool', return_value={"status": "ok", "updated_count": 50})

    cluster_id_to_label = "cluster_1"
    label_payload = {"new_label": 1} # Mark as Anomaly

    response = authenticated_client.post(f"/api/review/clusters/{cluster_id_to_label}", json=label_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["updated_count"] == 50

def test_get_logs_in_cluster(authenticated_client, mocker):
    """
    Tests fetching the individual logs that belong to a specific cluster.
    """
    fake_logs = [
        {"id": 101, "content": "Failed password for root"},
        {"id": 102, "content": "Failed password for admin"}
    ]
    mocker.patch('app.api.review.run_in_threadpool', return_value=fake_logs)

    response = authenticated_client.get("/api/review/clusters/cluster_1/logs")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[1]["content"] == "Failed password for admin"
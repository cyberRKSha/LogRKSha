# tests/test_worker.py
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from scripts import worker

def test_process_log_anomaly_flow(mocker):
    """
    Tests the entire logic flow of process_log when an anomaly is detected.
    """
    # --- 1. SETUP: Mock all external dependencies ---
    
    # Replace the actual model variables with mock objects
    mocker.patch.object(worker, 'embedder', Mock())
    mocker.patch.object(worker, 'supervised_model', Mock())
    mocker.patch.object(worker, 'unsupervised_model', Mock())
    mocker.patch.object(worker, 'lstm_model', Mock())
    mocker.patch.object(worker, 'unsupervised_threshold', 0.5)
    
    # Mock the functions that would be called on these objects
    worker.embedder.encode.return_value = [[0.1] * 384]
    worker.supervised_model.predict.return_value = [1]  # 1 = Anomaly
    worker.unsupervised_model.predict.return_value = [[0.1] * 384]

    # Mock other dependencies
    mocker.patch.object(worker, 'known_hashes', set())
    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch('scripts.worker.is_new_log_and_save_hash', return_value=True)
    mocker.patch('scripts.worker.load_models')
    mocker.patch('scripts.worker.sigma_engine.check_log', return_value=None)
    mocker.patch('scripts.worker.update_and_predict_sequence', return_value=0.5)
    fake_timestamp = datetime.now()
    mock_insert_db = mocker.patch('scripts.worker.insert_log_to_db', return_value=(12345, fake_timestamp))
    mock_map_attack = mocker.patch('scripts.worker.map_log_to_attack', return_value={"description": "Test Attack"})
    mock_send_dashboard = mocker.patch('scripts.worker.send_to_dashboard')
    mock_run_playbooks = mocker.patch('scripts.worker.run_playbooks')
    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection
    # We need to mock the final .scalar_one_or_none() call to return a fake alert ID (e.g., 1)
    mock_connection.execute.return_value.scalar_one_or_none.return_value = 1
    mocker.patch('scripts.worker.create_engine', return_value=mock_engine)
    
    # --- 2. ACT: Run the function with a sample log line ---
    test_log_line = "Sep 18 10:00:00 server sshd[1234]: Failed password for root"
    worker.process_log(source="auth.log", line=test_log_line)

    # --- 3. ASSERT: Check that the function behaved as expected ---
    mock_insert_db.assert_called_once()
    mock_map_attack.assert_called_once_with(test_log_line)
    mock_run_playbooks.assert_called_once()
    mock_send_dashboard.assert_called_once()

    final_payload = mock_send_dashboard.call_args[0][0]
    assert final_payload['is_alert'] is True
    assert final_payload['verdict'] == 'Supervised'
    assert final_payload['alert_info']['rule_description'] == "Test Attack"
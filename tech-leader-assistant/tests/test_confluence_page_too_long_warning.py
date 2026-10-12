import pytest
from app.tasks import confluence_page_too_long_warning_task

@pytest.fixture
def mock_settings(mocker):
    mock_settings_obj = mocker.MagicMock()
    mock_settings_obj.get.side_effect = lambda key, default=None: "ENG" if key == "CONFLUENCE_TRACKED_SPACES" else default
    mocker.patch('app.tasks.settings', mock_settings_obj, create=True)
    mocker.patch('app.clients.settings', mock_settings_obj, create=True)
    return mock_settings_obj

@pytest.fixture
def mock_confluence_client_class(mocker):
    mock_class = mocker.patch('app.clients.confluence_client.ConfluenceClient')
    mock_instance = mocker.MagicMock()
    mock_class.return_value = mock_instance
    return mock_instance

def test_confluence_page_too_long_warning_task(mock_settings, mock_confluence_client_class):
    # Setup mock data for long page
    mock_confluence_client_class.get_all_pages_from_space.return_value = {
        'results': [
            {
                'id': '123',
                'body': {'storage': {'value': 'a' * 10001}},
                'history': {'lastUpdated': {'by': {'accountId': 'user123'}}}
            }
        ]
    }

    # Setup mock data for comments (no existing warning)
    mock_confluence_client_class.get_page_comments.return_value = {
        'results': [
            {'body': {'storage': {'value': 'Looks good!'}}}
        ]
    }

    # Execute task
    confluence_page_too_long_warning_task()

    # Assertions
    mock_confluence_client_class.get_all_pages_from_space.assert_called_once_with('ENG', expand='body.storage,version,history.lastUpdated')
    mock_confluence_client_class.get_page_comments.assert_called_once_with('123')

    warning_text = "This page seems exceptionally long. Consider splitting it into smaller, more focused sub-pages to improve readability and maintainability."
    mock_confluence_client_class.add_page_comment.assert_called_once_with('123', f"[~accountid:user123] {warning_text}")

def test_confluence_page_too_long_already_warned(mock_settings, mock_confluence_client_class):
    # Setup mock data for long page
    mock_confluence_client_class.get_all_pages_from_space.return_value = {
        'results': [
            {
                'id': '456',
                'body': {'storage': {'value': 'a' * 10001}},
                'history': {'lastUpdated': {'by': {'accountId': 'user456'}}}
            }
        ]
    }

    # Setup mock data for comments WITH existing warning
    warning_text = "This page seems exceptionally long. Consider splitting it into smaller, more focused sub-pages to improve readability and maintainability."
    mock_confluence_client_class.get_page_comments.return_value = {
        'results': [
            {'body': {'storage': {'value': f"Hey, {warning_text}"}}}
        ]
    }

    # Execute task
    confluence_page_too_long_warning_task()

    # Assertions
    mock_confluence_client_class.add_page_comment.assert_not_called()

def test_confluence_page_not_too_long(mock_settings, mock_confluence_client_class):
    # Setup mock data for short page
    mock_confluence_client_class.get_all_pages_from_space.return_value = {
        'results': [
            {
                'id': '789',
                'body': {'storage': {'value': 'Short page'}},
                'history': {'lastUpdated': {'by': {'accountId': 'user789'}}}
            }
        ]
    }

    # Execute task
    confluence_page_too_long_warning_task()

    # Assertions
    mock_confluence_client_class.get_page_comments.assert_not_called()
    mock_confluence_client_class.add_page_comment.assert_not_called()

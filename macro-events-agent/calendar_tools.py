from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo
import datetime
import os

load_dotenv()

# Scopes for the Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']
MACRO_AGENT_CALENDAR_ID = os.getenv("MACRO_AGENT_CALENDAR_ID")
NYC_TIME_ZONE = 'America/New_York'

def authenticate_google_calendar(token_path, credentials_path):
    """Authenticate and return the Google Calendar API service."""
    creds = None

    # Load existing credentials if available
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If no valid credentials, authenticate the user
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future use
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def get_calendars(service):
    calendars = []
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar in calendar_list['items']:
            calendars.append(calendar)
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    return calendars

def get_calendar_id_map(service):
    calendars = get_calendars(service)
    calendar_id_map = {calendar['summary']: calendar['id'] for calendar in calendars}

    return calendar_id_map

def get_prev_day_7_am_notification_minutes(start_datetime):
    # Define custom notification (7 AM the day before the event)
    event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
    notification_time = (event_date - datetime.timedelta(days=1)).replace(hour=7, minute=0, second=0)
    notification_minutes = int((event_date - notification_time).total_seconds() // 60)

    return notification_minutes

def get_same_day_7_am_notification_minutes(start_datetime):
    # Define custom notification (7 AM the day of the event)
    event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
    notification_time = (event_date - datetime.timedelta(days=0)).replace(hour=7, minute=0, second=0)
    notification_minutes = int((event_date - notification_time).total_seconds() // 60)

    return notification_minutes

def get_num_days_notification_minutes(start_datetime, num_days):
    # Define custom notification (7 AM the day of the event)
    event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
    notification_time = (event_date - datetime.timedelta(days=num_days)).replace(hour=7, minute=0, second=0)
    notification_minutes = int((event_date - notification_time).total_seconds() // 60)

    return notification_minutes

def get_default_notification_30_minutes(start_datetime):
    # Define default notification (30 minutes before the event)
    event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
    notification_time = event_date - datetime.timedelta(minutes=30)
    notification_minutes = int((event_date - notification_time).total_seconds() // 60)

    return notification_minutes

def create_event(
    service,
    summary,
    description,
    start_datetime,
    end_datetime=None,
    add_default_notification=False,
    add_7_am_notifications=False,
    num_days_notifications=[],
    timezone=NYC_TIME_ZONE,
    calendar_id=MACRO_AGENT_CALENDAR_ID
):
    # TODO: What is the best way to handle this?
    # Ensure timezone-aware datetime
    if end_datetime is None:
        # Parse the start time
        start_dt = datetime.datetime.fromisoformat(start_datetime)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=ZoneInfo(timezone))
        # Add 30 minutes for default end time
        end_dt = start_dt + datetime.timedelta(minutes=30)
        end_datetime = end_dt.isoformat()

    """Create a new event in Google Calendar."""
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_datetime,
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_datetime,
            'timeZone': timezone,
        },
    }

    notifications = []
    if add_default_notification:
        notifications.append(
            {'method': 'popup', 'minutes': get_default_notification_30_minutes(start_datetime)}
        )

    if add_7_am_notifications:
        notifications.append(
            {'method': 'popup', 'minutes': get_prev_day_7_am_notification_minutes(start_datetime)}
        )
        notifications.append(
            {'method': 'popup', 'minutes': get_same_day_7_am_notification_minutes(start_datetime)}
        )

    if num_days_notifications:
        for num_days in num_days_notifications:
            notifications.append(
                {'method': 'popup', 'minutes': get_num_days_notification_minutes(start_datetime, num_days)}
            )

    if notifications:
        event['reminders'] = {
            'useDefault': False,
            'overrides': notifications
        }

    created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
    print(f"Event created: id - {created_event.get('id')}, html_link - {created_event.get('htmlLink')}")
    return created_event

def delete_event(
    service,
    event_id,
    calendar_id=MACRO_AGENT_CALENDAR_ID
):
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    print(f"Event with ID {event_id} deleted successfully.")

def delete_events_with_prefix(
    service,
    start_time,
    end_time,
    summary_prefix,
):
    events = get_events(service, start_time, end_time)
    events_to_delete = [event for event in events if event['summary'].startswith(summary_prefix)]
    print(f"Number of events to delete = {len(events_to_delete)}")

    for event_to_delete in events_to_delete:
        delete_event(service, event_to_delete['id'])

def get_events(
    service,
    start_time,
    end_time,
    singleEvents=True,
    calendar_id=MACRO_AGENT_CALENDAR_ID
):
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time.isoformat() + 'Z',  # 'Z' indicates UTC time
        timeMax=end_time.isoformat() + 'Z',
        maxResults=2500,  # Adjust as needed
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])
    events = [{
        'etag': event['etag'],
        'id': event['id'],
        'summary': event['summary'],
        'description': event['description'],
        'start': event['start'],
        'end': event['end'],
        'reminders': event['reminders'],
        'html_link': event['htmlLink'],
    } for event in events_result]
    print(f"Number of events = {len(events)}")

    return events

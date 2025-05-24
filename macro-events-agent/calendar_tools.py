from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from typing import List, Optional
from utils import logger
from zoneinfo import ZoneInfo
import datetime
import os

load_dotenv()


class GoogleCalendar:
    # Scopes for the Google Calendar API
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    MACRO_AGENT_CALENDAR_ID = os.getenv("MACRO_AGENT_CALENDAR_ID")
    NYC_TIME_ZONE = 'America/New_York'

    def __init__(
        self,
        token_path: str,
        credentials_path: str,
        calendar_id: Optional[str] = None, # Defaults to MACRO_AGENT_CALENDAR_ID
        timezone: Optional[str] = None
    ):
        try:
            creds = None
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(credentials_path):
                        raise FileNotFoundError(f"Credentials file not found at {credentials_path}")
                    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, self.SCOPES)
                    creds = flow.run_local_server(port=0)

                with open(token_path, 'w') as token_file:
                    token_file.write(creds.to_json())

            self.service = build('calendar', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to authenticate or build Google Calendar service: {e}")
            raise

        self.calendar_id = calendar_id if calendar_id else self.MACRO_AGENT_CALENDAR_ID
        if not self.calendar_id:
            logger.warning("MACRO_AGENT_CALENDAR_ID is not set in .env and no calendar_id provided.")

        self.timezone = timezone if timezone else self.NYC_TIME_ZONE

    def get_calendars(self):
        calendars = []
        page_token = None
        try:
            while True:
                calendar_list = self.service.calendarList().list(pageToken=page_token).execute()
                calendars.extend(calendar_list.get('items', []))
                page_token = calendar_list.get('nextPageToken')
                if not page_token:
                    break
        except Exception as e:
            logger.error(f"Error fetching calendars: {e}")

        return calendars

    def get_calendar_id_map(self):
        calendars = self.get_calendars()
        calendar_id_map = {calendar['summary']: calendar['id'] for calendar in calendars}

        return calendar_id_map

    def get_prev_day_7_am_notification_minutes(self, start_datetime):
        # Define custom notification (7 AM the day before the event)
        event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
        notification_time = (event_date - datetime.timedelta(days=1)).replace(hour=7, minute=0, second=0)
        notification_minutes = int((event_date - notification_time).total_seconds() // 60)

        return notification_minutes

    def get_same_day_7_am_notification_minutes(self, start_datetime):
        # Define custom notification (7 AM the day of the event)
        event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
        notification_time = (event_date - datetime.timedelta(days=0)).replace(hour=7, minute=0, second=0)
        notification_minutes = int((event_date - notification_time).total_seconds() // 60)

        return notification_minutes

    def get_num_days_notification_minutes(self, start_datetime, num_days):
        # Define custom notification (7 AM the day of the event)
        event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
        notification_time = (event_date - datetime.timedelta(days=num_days)).replace(hour=7, minute=0, second=0)
        notification_minutes = int((event_date - notification_time).total_seconds() // 60)

        return notification_minutes

    def get_default_notification_30_minutes(self, start_datetime):
        # Define default notification (30 minutes before the event)
        event_date = datetime.datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S')
        notification_time = event_date - datetime.timedelta(minutes=30)
        notification_minutes = int((event_date - notification_time).total_seconds() // 60)

        return notification_minutes

    def create_event(
        self,
        summary: str,
        description: str,
        start_datetime: str,
        end_datetime: Optional[str] =None,
        add_default_notification: bool =False,
        add_7_am_notifications: bool =False,
        num_days_notifications: Optional[List[int]] =None,
        timezone: Optional[str] = None,
        calendar_id: Optional[str] = None
    ):
        if num_days_notifications is None:
            num_days_notifications = []

        current_calendar_id: str = calendar_id if calendar_id else self.calendar_id
        current_timezone: str = timezone if timezone else self.timezone

        # TODO: What is the best way to handle this?
        if end_datetime is None:
            start_dt = datetime.datetime.fromisoformat(start_datetime)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=ZoneInfo(current_timezone))
            # Add 30 minutes for default end time
            end_dt = start_dt + datetime.timedelta(minutes=30)
            end_datetime = end_dt.isoformat()

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_datetime,
                'timeZone': current_timezone,
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': current_timezone,
            },
        }

        notifications = []
        if add_default_notification:
            notifications.append(
                {'method': 'popup', 'minutes': self.get_default_notification_30_minutes(start_datetime)}
            )

        if add_7_am_notifications:
            notifications.append(
                {'method': 'popup', 'minutes': self.get_prev_day_7_am_notification_minutes(start_datetime)}
            )
            notifications.append(
                {'method': 'popup', 'minutes': self.get_same_day_7_am_notification_minutes(start_datetime)}
            )

        if num_days_notifications:
            for num_days in num_days_notifications:
                notifications.append(
                    {'method': 'popup', 'minutes': self.get_num_days_notification_minutes(start_datetime, num_days)}
                )

        if notifications:
            event['reminders'] = {
                'useDefault': False,
                'overrides': notifications
            }

        try:
            created_event = self.service.events().insert(calendarId=current_calendar_id, body=event).execute()
            logger.info(f"Event created: id - {created_event.get('id')}, html_link - {created_event.get('htmlLink')}")
            return created_event
        except Exception as e:
            logger.error(f"Failed to create event in calendar '{current_calendar_id}': {e}")
            return None

    def delete_event(
        self,
        event_id: str,
        calendar_id: Optional[str] = None
    ):
        current_calendar_id: str = calendar_id if calendar_id else self.calendar_id

        try:
            self.service.events().delete(calendarId=current_calendar_id, eventId=event_id).execute()
            logger.info(f"Event with ID {event_id} deleted successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete event {event_id} from calendar '{current_calendar_id}': {e}")
            return False

    def get_events(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        singleEvents: bool = True,
        calendar_id: Optional[str] = None
    ):
        current_calendar_id: str = calendar_id if calendar_id else self.calendar_id

        try:
            events_result = self.service.events().list(
                calendarId=current_calendar_id,
                # TODO: Fix the time zone here
                timeMin=start_time.isoformat() + 'Z',  # 'Z' indicates UTC time
                timeMax=end_time.isoformat() + 'Z',
                maxResults=2500,
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
            logger.info(f"Number of events = {len(events)}")

            return events
        except Exception as e:
            logger.error(f"Failed to get events from calendar '{current_calendar_id}': {e}")
            return []

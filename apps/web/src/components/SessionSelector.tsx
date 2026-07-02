import { useState } from 'react';
import { useSessions } from '../hooks/useSessions';
import { useAppContext } from '../context/AppContext';
import { Meeting } from '../types/session';

const YEARS = [2023, 2024, 2025, 2026];

function MeetingItem({
  meeting,
  onSessionSelect,
}: {
  meeting: Meeting;
  onSessionSelect: (key: number, name: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li className="meeting-item">
      <button
        className="meeting-header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="meeting-name">{meeting.meeting_name}</span>
        <span className="meeting-location">
          {meeting.country_name} — {meeting.location}
        </span>
      </button>
      {expanded && (
        <ul className="session-list">
          {meeting.sessions.map((session) => (
            <li key={session.session_key}>
              <button
                className="session-button"
                onClick={() =>
                  onSessionSelect(
                    session.session_key,
                    `${meeting.meeting_name} — ${session.session_name}`,
                  )
                }
              >
                {session.session_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function SessionSelector() {
  const [year, setYear] = useState<number>(2024);
  const [filter, setFilter] = useState('');
  const { data: meetings, isLoading, error, refetch } = useSessions(year);
  const { selectSession } = useAppContext();

  const filteredMeetings = meetings?.filter((m) =>
    m.country_name.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="session-selector">
      <div className="session-selector-controls">
        <label>
          Year:
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {YEARS.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <input
          type="text"
          placeholder="Filter by country..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {isLoading && <p className="loading-message">Loading sessions…</p>}

      {error && (
        <div className="error-state">
          <p>Unable to load sessions</p>
          <button onClick={() => refetch()}>Retry</button>
        </div>
      )}

      {filteredMeetings && (
        <ul className="meetings-list">
          {filteredMeetings.map((meeting) => (
            <MeetingItem
              key={meeting.meeting_key}
              meeting={meeting}
              onSessionSelect={selectSession}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

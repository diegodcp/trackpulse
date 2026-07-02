import { useState, useMemo } from 'react';
import { useSessions } from '../hooks/useSessions';
import { useAppContext } from '../context/AppContext';
import { Meeting, SessionInfo } from '../types/session';
import './SessionSelector.css';

const YEARS = [2023, 2024, 2025, 2026];

function SessionCard({
  session,
  meetingName,
  onSelect,
}: {
  session: SessionInfo;
  meetingName: string;
  onSelect: (key: number, name: string) => void;
}) {
  const typeClass = session.session_type.toLowerCase().replace(/\s+/g, '-');
  return (
    <button
      className={`session-card session-card--${typeClass}`}
      onClick={() =>
        onSelect(session.session_key, `${meetingName} — ${session.session_name}`)
      }
    >
      <span className="session-card__name">{session.session_name}</span>
      <span className="session-card__date">
        {new Date(session.date_start).toLocaleDateString(undefined, {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
        })}
      </span>
    </button>
  );
}

function MeetingRow({
  meeting,
  onSessionSelect,
}: {
  meeting: Meeting;
  onSessionSelect: (key: number, name: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li className={`meeting-row ${expanded ? 'meeting-row--expanded' : ''}`}>
      <button
        className="meeting-row__header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <div className="meeting-row__info">
          <span className="meeting-row__name">{meeting.meeting_name}</span>
          <span className="meeting-row__location">
            {meeting.country_name} · {meeting.location}
          </span>
        </div>
        <div className="meeting-row__meta">
          <span className="meeting-row__date">
            {new Date(meeting.date_start).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
            })}
          </span>
          <span className={`meeting-row__chevron ${expanded ? 'meeting-row__chevron--open' : ''}`}>
            ▾
          </span>
        </div>
      </button>
      {expanded && (
        <div className="meeting-row__sessions">
          {meeting.sessions.map((session) => (
            <SessionCard
              key={session.session_key}
              session={session}
              meetingName={meeting.meeting_name}
              onSelect={onSessionSelect}
            />
          ))}
        </div>
      )}
    </li>
  );
}

export function SessionSelector() {
  const [year, setYear] = useState<number>(2024);
  const [selectedCircuit, setSelectedCircuit] = useState<string>('');
  const { data: meetings, isLoading, error, refetch } = useSessions(year);
  const { selectSession } = useAppContext();

  const circuits = useMemo(() => {
    if (!meetings) return [];
    return [...new Set(meetings.map((m) => m.circuit_short_name))].sort();
  }, [meetings]);

  const filteredMeetings = useMemo(() => {
    if (!meetings) return [];
    if (!selectedCircuit) return meetings;
    return meetings.filter((m) => m.circuit_short_name === selectedCircuit);
  }, [meetings, selectedCircuit]);

  return (
    <div className="session-selector">
      <div className="session-selector__topbar">
        <div className="session-selector__brand">
          <span className="session-selector__title">Session Select</span>
        </div>
        <div className="session-selector__controls">
          <select
            className="session-selector__select"
            value={year}
            onChange={(e) => {
              setYear(Number(e.target.value));
              setSelectedCircuit('');
            }}
          >
            {YEARS.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <select
            className="session-selector__select"
            value={selectedCircuit}
            onChange={(e) => setSelectedCircuit(e.target.value)}
            disabled={!meetings || meetings.length === 0}
          >
            <option value="">All Circuits</option>
            {circuits.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="session-selector__content">
        {isLoading && (
          <div className="session-selector__loading">
            <div className="spinner" />
            <p>Loading sessions…</p>
          </div>
        )}

        {error && (
          <div className="session-selector__error">
            <p>Unable to load sessions</p>
            <button className="btn-retry" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        )}

        {!isLoading && !error && filteredMeetings.length === 0 && meetings && (
          <div className="session-selector__empty">
            <p>No meetings found</p>
          </div>
        )}

        {filteredMeetings.length > 0 && (
          <ul className="session-selector__list">
            {filteredMeetings.map((meeting) => (
              <MeetingRow
                key={meeting.meeting_key}
                meeting={meeting}
                onSessionSelect={selectSession}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

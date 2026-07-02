import { describe, it, expect } from 'vitest';
import { formatTime } from '../src/utils/formatTime';

describe('formatTime', () => {
  it('formats seconds only', () => {
    expect(formatTime(45)).toBe('00:45');
  });

  it('formats minutes and seconds', () => {
    expect(formatTime(125)).toBe('02:05');
  });

  it('formats hours', () => {
    expect(formatTime(3661)).toBe('1:01:01');
  });

  it('handles zero', () => {
    expect(formatTime(0)).toBe('00:00');
  });

  it('handles race duration', () => {
    expect(formatTime(5520)).toBe('1:32:00');
  });

  it('floors fractional seconds', () => {
    expect(formatTime(62.7)).toBe('01:02');
  });
});

// UTC prevents local timezone and DST changes from moving calendar dates.
export function calendarMonth(month) {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month || '')) return null;
  const first = new Date(`${month}-01T12:00:00Z`);
  if (!Number.isFinite(first.getTime())) return null;
  const last = new Date(first);
  last.setUTCMonth(last.getUTCMonth() + 1);
  last.setUTCDate(0);
  const dayCount = last.getUTCDate();
  const offset = (first.getUTCDay() + 6) % 7;
  const cells = Array.from({ length: Math.ceil((offset + dayCount) / 7) * 7 }, (_, index) => {
    const day = index - offset + 1;
    return day < 1 || day > dayCount ? null : `${month}-${String(day).padStart(2, '0')}`;
  });
  return { dayCount, offset, cells, firstDate: `${month}-01`, lastDate: `${month}-${dayCount}` };
}

export function monthLabel(month) {
  if (!calendarMonth(month)) return '';
  return new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${month}-01T12:00:00Z`));
}

export function dateLabel(date, options = {}) {
  const parsed = new Date(`${date}T12:00:00Z`);
  if (!Number.isFinite(parsed.getTime())) return date || '';
  return new Intl.DateTimeFormat('en', {
    weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC', ...options,
  }).format(parsed);
}

export function belongsToMonth(date, month) {
  const calendar = calendarMonth(month);
  return Boolean(calendar && /^\d{4}-\d{2}-\d{2}$/.test(date || '')
    && date >= calendar.firstDate && date <= calendar.lastDate);
}

import { format, formatInTimeZone, toZonedTime } from 'date-fns-tz'
import { format as formatDate, isToday, isYesterday, subDays, differenceInDays, parse } from 'date-fns'

// Get user's timezone
export const getUserTimeZone = (): string => {
  // Prefer user-configured timezone when available.
  const userTimezone = localStorage.getItem('timezone')
  if (userTimezone) {
    return userTimezone
  }
  // Fall back to browser timezone when not configured.
  const zoned = Intl.DateTimeFormat().resolvedOptions().timeZone
  return zoned
}

// Convert timestamp to zoned date object
export const timestampToZonedDate = (timestamp: number | string): Date => {
  const timeZone = getUserTimeZone()
  const date = new Date(Number(timestamp) * 1000)
  return toZonedTime(date, timeZone)
}

// Convert ISO string to zoned date object
export const isoToZonedDate = (isoString: string): Date => {
  const timeZone = getUserTimeZone()
  return toZonedTime(new Date(isoString), timeZone)
}

// Format date time with timezone
export const formatDateTime = (date: Date, formatStr: string = 'yyyy-MM-dd HH:mm:ss'): string => {
  const timeZone = getUserTimeZone()
  return formatInTimeZone(date, timeZone, formatStr)
}

// Parse datetime string with timezone
export const parseDateTime = (dateStr: string, formatStr: string = 'yyyy-MM-dd HH:mm:ss'): Date => {
  const timeZone = getUserTimeZone()
  const date = parse(dateStr, formatStr, new Date())
  return toZonedTime(date, timeZone)
}

// Convert date to UTC
export const toUTC = (date: Date): Date => {
  // Use native Date conversion for UTC.
  return new Date(date.toISOString())
}

// Convert UTC date to local timezone
export const fromUTC = (date: Date): Date => {
  const timeZone = getUserTimeZone()
  return toZonedTime(date, timeZone)
}

// Format relative time (e.g., Today, Yesterday, etc.)
export const formatRelativeTime = (date: Date): string => {
  const now = new Date()
  const timeZone = getUserTimeZone()
  const zonedDate = toZonedTime(date, timeZone)
  const zonedNow = toZonedTime(now, timeZone)

  if (isToday(zonedDate)) {
    return formatInTimeZone(zonedDate, timeZone, 'HH:mm')
  } else if (isYesterday(zonedDate)) {
    return 'Yesterday'
  } else if (differenceInDays(zonedNow, zonedDate) <= 7) {
    return formatInTimeZone(zonedDate, timeZone, 'EEEE')
  } else {
    return formatInTimeZone(zonedDate, timeZone, 'yyyy-MM-dd')
  }
}

// Get date group title for conversation grouping
export const getDateGroupTitle = (date: Date): string => {
  const timeZone = getUserTimeZone()
  const zonedDate = toZonedTime(date, timeZone)
  const now = toZonedTime(new Date(), timeZone)

  if (isToday(zonedDate)) {
    return 'Today'
  } else if (isYesterday(zonedDate)) {
    return 'Yesterday'
  } else if (differenceInDays(now, zonedDate) <= 3) {
    return 'Last 3 Days'
  } else if (differenceInDays(now, zonedDate) <= 7) {
    return 'Last Week'
  } else {
    return formatInTimeZone(zonedDate, timeZone, 'yyyy-MM-dd')
  }
}

// Convert date to UTC timestamp (in seconds)
export const dateToUTCTimestamp = (date: Date): number => {
  return Math.floor(date.getTime() / 1000)
}

// Convert UTC timestamp (in seconds) to local date
export const utcTimestampToLocalDate = (utcTimestamp: number): Date => {
  return new Date(utcTimestamp * 1000)
}

// Convert local timestamp (in seconds) to UTC timestamp
export const localTimestampToUTCTimestamp = (localTimestamp: number): number => {
  const date = new Date(localTimestamp * 1000)
  return Math.floor(date.getTime() / 1000)
} 

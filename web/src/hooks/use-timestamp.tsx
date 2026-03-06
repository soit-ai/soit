'use client'
import { useCallback } from 'react'
import { formatInTimeZone, toZonedTime } from 'date-fns-tz'
import { getUserTimeZone } from '@/utils/date-time'

export const useTimestamp = () => {
  const formatTime = useCallback((value: number, format: string) => {
    const timeZone = getUserTimeZone()
    const date = new Date(value * 1000)
    return formatInTimeZone(date, timeZone, format)
  }, [])

  const formatDate = useCallback((value: string, format: string) => {
    const timeZone = getUserTimeZone()
    const date = new Date(value)
    return formatInTimeZone(date, timeZone, format)
  }, [])

  const formatDateTime = useCallback((date: Date, format: string) => {
    const timeZone = getUserTimeZone()
    return formatInTimeZone(date, timeZone, format)
  }, [])

  const toZonedDate = useCallback((date: Date | string | number) => {
    const timeZone = getUserTimeZone()
    if (typeof date === 'string') {
      return toZonedTime(new Date(date), timeZone)
    } else if (typeof date === 'number') {
      return toZonedTime(new Date(date * 1000), timeZone)
    }
    return toZonedTime(date, timeZone)
  }, [])

  return { formatTime, formatDate, formatDateTime, toZonedDate }
}

export default useTimestamp

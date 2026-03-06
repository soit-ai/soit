// javascript
import { nanoid, customAlphabet } from 'nanoid'
import { ulid } from 'ulid'

// Convert nanoid to uuidv4 format
const uuidv4 = () => {
  // Generate a random string of length 32
  let randomString = nanoid(36)
  // Remove all '-' and '_' from the random string
  randomString = randomString.replace(/-/g, '').replace(/_/g, '')
  // Convert random string to UUID format
  const uuid = `${randomString.slice(0, 8)}-${randomString.slice(8, 12)}-${randomString.slice(12, 16)}-${randomString.slice(16, 20)}-${randomString.slice(20)}`
  // to strlower
  return uuid.toLowerCase()
}

const uuidv7 = () => {
  let randomString = nanoid(36)
  // Remove all '-' and '_' from the random string
  randomString = randomString.replace(/-/g, '').replace(/_/g, '')
  // Convert random string to UUID format
  const uuid = `${randomString.slice(0, 8)}-${randomString.slice(8, 12)}-${randomString.slice(12, 16)}-${randomString.slice(16, 20)}-${randomString.slice(20)}`
  // to strlower
  return uuid.toLowerCase()
}

// return a random string
const getAppid = (type?: string) => {
  const nanoida = customAlphabet('1234567890', 10)
  const _ext = nanoida(3)
  // Append current timestamp.
  const _time = parseInt(Date.now() / 1000 + '').toString()
  const _str = _time + '' + _ext
  return _str
}

export { uuidv4, uuidv7, nanoid, ulid, getAppid }

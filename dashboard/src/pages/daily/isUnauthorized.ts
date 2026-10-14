import axios from "axios"

export function isUnauthorized(...errors: unknown[]): boolean {
  return errors.some((error) => axios.isAxiosError(error) && error.response?.status === 401)
}

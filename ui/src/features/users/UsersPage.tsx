import { FormEvent, useEffect, useState } from 'react'

import { UserItem, createUser, deleteUser, getCurrentUser, listUsers } from '../../shared/api/client'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'
import { formatDateTime } from '../../shared/format/datetime'

export function UsersPage() {
  const { timezone } = useOperatorPreferences()
  const [items, setItems] = useState<UserItem[]>([])
  const [currentUser, setCurrentUser] = useState<UserItem | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [deletingUsername, setDeletingUsername] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [users, me] = await Promise.all([listUsers(), getCurrentUser()])
      setItems(users)
      setCurrentUser(me)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const onCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const username = String(form.get('username') || '').trim()
    const password = String(form.get('password') || '')
    const confirmPassword = String(form.get('confirm_password') || '')
    const isAdmin = form.get('is_admin') === 'on'

    if (!username) {
      setError('Username is required')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setCreating(true)
    setError(null)
    setSuccess(null)
    try {
      await createUser({
        username,
        password,
        is_admin: isAdmin,
      })
      formElement.reset()
      setSuccess(`User ${username} created.`)
      await refresh()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Failed to create user')
    } finally {
      setCreating(false)
    }
  }

  const onDelete = async (targetUsername: string) => {
    setDeletingUsername(targetUsername)
    setError(null)
    setSuccess(null)
    try {
      await deleteUser(targetUsername)
      setSuccess(`User ${targetUsername} deleted.`)
      await refresh()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete user')
    } finally {
      setDeletingUsername(null)
    }
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Users</h2>
          <p className="muted">Manage built-in control-plane accounts for operators and administrators.</p>
        </div>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      <form className="card builder-section" onSubmit={onCreate}>
        <h3>Create User</h3>
        <div className="inline-grid">
          <label>
            Username
            <input autoComplete="username" name="username" />
          </label>
          <label>
            Password
            <input autoComplete="new-password" name="password" type="password" />
          </label>
          <label>
            Confirm Password
            <input autoComplete="new-password" name="confirm_password" type="password" />
          </label>
          <label className="toggle-label">
            <input name="is_admin" type="checkbox" />
            Admin access
          </label>
        </div>
        <p className="muted">Built-in passwords must be at least 12 characters long and include both letters and numbers.</p>
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}
        <button className="btn" disabled={creating} type="submit">
          {creating ? 'Creating...' : 'Create User'}
        </button>
      </form>

      {loading && <p>Loading users...</p>}

      {!loading && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const isCurrentUser = currentUser?.username === item.username
                return (
                  <tr key={item.username}>
                    <td>
                      {item.username}
                      {isCurrentUser && <div className="muted">Current session</div>}
                    </td>
                    <td>{item.is_admin ? 'Admin' : item.roles.join(', ')}</td>
                    <td>{formatDateTime(item.created_at, timezone, { includeTimezone: true })}</td>
                    <td>
                      <button
                        className="btn btn-secondary"
                        disabled={deletingUsername === item.username || isCurrentUser}
                        onClick={() => void onDelete(item.username)}
                        type="button"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              })}
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

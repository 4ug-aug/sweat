# Frontend Designer

## Stack
- **UI Components:** shadcn/ui
- **Styling:** Tailwind CSS (high density, tight margins)
- **Routing:** TanStack Router
- **HTTP:** Unified `api.js` Axios instance
- **State Management:** Zustand (cross-component shared state only)

---

## Design Philosophy

### Density & Spacing
- Default to `text-sm` for body copy, `text-xs` for metadata and labels
- Use `gap-2`, `gap-3` and `p-2`, `p-3` as defaults — reach for `p-4`+ only when breathing room is intentional (modals, empty states)
- Prefer `h-8` for inputs and buttons (`size="sm"` in shadcn). Use default size only for primary CTAs
- Tables: `py-1.5 px-3` for `<td>`, `text-xs font-medium uppercase tracking-wide text-muted-foreground` for `<th>`
- Cards: use `p-3` or `p-4`, never default shadcn `p-6` unless it's a hero/marketing card
- Avoid vertical whitespace sprawl — stack sections with `space-y-3` or `space-y-4`, not `space-y-8`

### Component Defaults
Always override shadcn defaults toward tighter variants:
```tsx
// Prefer
<Button size="sm" variant="outline">Action</Button>
<Input className="h-8 text-sm" />
<Badge className="text-xs px-1.5 py-0" />

// Avoid (too much padding for dense UIs)
<Button>Action</Button>
<Input />
```

---

## File & Folder Conventions

```
src/
├── api/
│   └── api.js              # Unified Axios instance
├── routes/
│   ├── __root.tsx
│   ├── index.tsx
│   └── [feature]/
│       └── route.tsx
├── stores/
│   └── [feature]Store.js   # Zustand stores, one per domain
├── components/
│   ├── ui/                 # shadcn auto-generated (never edit)
│   └── [feature]/          # Feature-specific components
└── lib/
    └── utils.js            # cn() and other helpers
```

---

## api.js — Unified Axios Instance

Always import from `@/api/api.js`. Never create ad-hoc `axios.get()` calls.

```js
// src/api/api.js
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// Attach auth token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Global error handling
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // redirect to login or clear session
    }
    return Promise.reject(err)
  }
)

export default api
```

**Usage pattern:**
```js
// In a component or store action
import api from '@/api/api'

const { data } = await api.get('/users')
await api.post('/users', payload)
await api.patch(`/users/${id}`, patch)
await api.delete(`/users/${id}`)
```

---

## TanStack Router

Use file-based routing. Each route file exports a `Route` created with `createFileRoute`.

```tsx
// src/routes/users/index.tsx
import { createFileRoute } from '@tanstack/react-router'
import { UsersPage } from '@/components/users/UsersPage'

export const Route = createFileRoute('/users/')({
  component: UsersPage,
})
```

**Navigation:**
```tsx
import { Link, useNavigate } from '@tanstack/react-router'

// Declarative
<Link to="/users/$id" params={{ id: user.id }} className="text-sm hover:underline">
  {user.name}
</Link>

// Imperative
const navigate = useNavigate()
navigate({ to: '/users/$id', params: { id } })
```

**Route params & search params:**
```tsx
export const Route = createFileRoute('/users/$id')({
  component: UserDetail,
})

// Inside component:
const { id } = Route.useParams()
const { tab } = Route.useSearch()
```

---

## Zustand — Shared State Only

Only use Zustand when state needs to be shared across components that are not in a direct parent-child relationship. Local UI state (open/close, hover, form values) stays in `useState`.

**Store pattern:**
```js
// src/stores/userStore.js
import { create } from 'zustand'
import api from '@/api/api'

export const useUserStore = create((set, get) => ({
  users: [],
  selectedUser: null,
  loading: false,
  error: null,

  fetchUsers: async () => {
    set({ loading: true, error: null })
    try {
      const { data } = await api.get('/users')
      set({ users: data, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },

  setSelectedUser: (user) => set({ selectedUser: user }),

  createUser: async (payload) => {
    const { data } = await api.post('/users', payload)
    set((state) => ({ users: [...state.users, data] }))
    return data
  },

  updateUser: async (id, patch) => {
    const { data } = await api.patch(`/users/${id}`, patch)
    set((state) => ({
      users: state.users.map((u) => (u.id === id ? data : u)),
    }))
  },

  deleteUser: async (id) => {
    await api.delete(`/users/${id}`)
    set((state) => ({ users: state.users.filter((u) => u.id !== id) }))
  },
}))
```

**Usage:**
```tsx
const { users, loading, fetchUsers } = useUserStore()

// Subscribe to a slice to avoid re-renders
const selectedUser = useUserStore((s) => s.selectedUser)
```

**When NOT to use Zustand:**
```tsx
// ✅ Fine as local state — only used in one component
const [open, setOpen] = useState(false)
const [query, setQuery] = useState('')

// ✅ Fine as local state — form values before submission
const [form, setForm] = useState({ name: '', email: '' })
```

---

## Component Anatomy (Dense Layout Example)

```tsx
// A typical list page
export function UsersPage() {
  const { users, loading, fetchUsers } = useUserStore()

  useEffect(() => { fetchUsers() }, [])

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold">Users</h1>
          <p className="text-xs text-muted-foreground">{users.length} total</p>
        </div>
        <Button size="sm">
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          Add User
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Name</TableHead>
              <TableHead className="text-xs">Email</TableHead>
              <TableHead className="text-xs w-[80px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={3} className="text-center text-xs text-muted-foreground py-6">
                  Loading…
                </TableCell>
              </TableRow>
            ) : users.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="text-sm font-medium py-1.5">{user.name}</TableCell>
                <TableCell className="text-sm text-muted-foreground py-1.5">{user.email}</TableCell>
                <TableCell className="py-1.5">
                  <Button variant="ghost" size="icon" className="h-7 w-7">
                    <MoreHorizontal className="h-3.5 w-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
```

---

## Shadcn Dialog / Sheet Pattern

Keep forms inside `Dialog` or `Sheet` for create/edit flows. Control open state locally.

```tsx
function CreateUserDialog() {
  const [open, setOpen] = useState(false)
  const { createUser } = useUserStore()
  const [form, setForm] = useState({ name: '', email: '' })

  const handleSubmit = async () => {
    await createUser(form)
    setOpen(false)
    setForm({ name: '', email: '' })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="mr-1.5 h-3.5 w-3.5" />Add User</Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-sm">New User</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3 py-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium">Name</label>
            <Input
              className="h-8 text-sm"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium">Email</label>
            <Input
              className="h-8 text-sm"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
          <Button size="sm" onClick={handleSubmit}>Create</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

---

## Key Rules Summary

| Rule | Guidance |
|---|---|
| Spacing | `p-2`/`p-3` default, `p-4` for intentional breathing room |
| Text size | `text-sm` body, `text-xs` metadata/labels/table headers |
| Buttons/inputs | `size="sm"`, `h-8` height as default |
| API calls | Always via `@/api/api.js`, never raw axios |
| Zustand | Only for cross-component shared state |
| Local state | `useState` for UI toggles, form values, hover |
| Routing | TanStack Router file-based, `Link` + `useNavigate` |
| shadcn components | Never edit `/components/ui/` — compose on top |
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LoginScreen from '../LoginScreen'

// Re-import mocked firebase functions
const firebase = await vi.importMock<typeof import('../firebase')>('../firebase')

describe('LoginScreen', () => {
  const mockOnLogin = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the company branding', () => {
    render(<LoginScreen onLogin={mockOnLogin} />)
    expect(screen.getByText('Gernetzke & Associates')).toBeInTheDocument()
    expect(screen.getByText('Financial Services Dashboard')).toBeInTheDocument()
  })

  it('renders sign-in heading and authorized notice', () => {
    render(<LoginScreen onLogin={mockOnLogin} />)
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText('Authorized personnel only.')).toBeInTheDocument()
  })

  it('renders email and password input fields', () => {
    render(<LoginScreen onLogin={mockOnLogin} />)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('renders Google sign-in button', () => {
    render(<LoginScreen onLogin={mockOnLogin} />)
    expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
  })

  it('renders Firebase security footer', () => {
    render(<LoginScreen onLogin={mockOnLogin} />)
    expect(screen.getByText('Secured by Firebase Authentication')).toBeInTheDocument()
  })

  it('shows error for unauthorized email on email login', async () => {
    const user = userEvent.setup()
    const mockUser = { email: 'hacker@evil.com', displayName: 'Hacker' }
    firebase.loginWithEmail.mockResolvedValue({ user: mockUser } as any)

    render(<LoginScreen onLogin={mockOnLogin} />)

    await user.type(screen.getByLabelText('Email'), 'hacker@evil.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Access denied. This email is not authorized.')).toBeInTheDocument()
    expect(mockOnLogin).not.toHaveBeenCalled()
  })

  it('calls onLogin for authorized email on email login', async () => {
    const user = userEvent.setup()
    const mockUser = { email: 'dean.barrett.86@gmail.com', displayName: 'Dean' }
    firebase.loginWithEmail.mockResolvedValue({ user: mockUser } as any)

    render(<LoginScreen onLogin={mockOnLogin} />)

    await user.type(screen.getByLabelText('Email'), 'dean.barrett.86@gmail.com')
    await user.type(screen.getByLabelText('Password'), 'secret123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(mockOnLogin).toHaveBeenCalledWith(mockUser)
  })

  it('shows error on invalid credentials', async () => {
    const user = userEvent.setup()
    firebase.loginWithEmail.mockRejectedValue(new Error('auth/invalid-credential'))

    render(<LoginScreen onLogin={mockOnLogin} />)

    await user.type(screen.getByLabelText('Email'), 'test@test.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument()
  })

  it('shows error on too many requests', async () => {
    const user = userEvent.setup()
    firebase.loginWithEmail.mockRejectedValue(new Error('auth/too-many-requests'))

    render(<LoginScreen onLogin={mockOnLogin} />)

    await user.type(screen.getByLabelText('Email'), 'test@test.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Too many attempts. Please try again later.')).toBeInTheDocument()
  })

  it('shows error for unauthorized email on Google login', async () => {
    const user = userEvent.setup()
    const mockUser = { email: 'nobody@gmail.com', displayName: 'Nobody' }
    firebase.loginWithGoogle.mockResolvedValue({ user: mockUser } as any)

    render(<LoginScreen onLogin={mockOnLogin} />)

    await user.click(screen.getByText('Sign in with Google'))

    expect(await screen.findByText('Access denied. This email is not authorized.')).toBeInTheDocument()
    expect(mockOnLogin).not.toHaveBeenCalled()
  })
})

import { beforeEach, describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import App from './App'

describe('LinguaAI app', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  it('shows authentication before the app for a new visitor', () => {
    render(<App />)
    expect(screen.getAllByRole('button', { name: 'Kirish' })).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Hisob yaratish' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Parolni unutdingizmi?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mehmon sifatida davom etish' })).toBeInTheDocument()
  })

  it('exposes automatic detection and all translation styles', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Mehmon sifatida davom etish' }))
    fireEvent.click(screen.getByRole('link', { name: 'Tarjimon' }))

    expect(screen.getByRole('group', { name: 'Manba tili' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Avtomatik/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Oddiy' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rasmiy' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Professional' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tillarni almashtirish' })).toHaveTextContent('⇄')
  })

  it('starts in the deep emerald theme and allows theme and sound toggles', () => {
    render(<App />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark-teal')
    fireEvent.click(screen.getByRole('button', { name: 'Moviy Okean mavzusiga o‘tish' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'ocean-teal')
    fireEvent.click(screen.getByRole('button', { name: 'Ovozli effektlarni o‘chirish' }))
    expect(screen.getByRole('button', { name: 'Ovozli effektlarni yoqish' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('supports showing and hiding passwords', () => {
    render(<App />)
    const password = screen.getByPlaceholderText('Kamida 6 ta belgi')
    expect(password).toHaveAttribute('type', 'password')
    fireEvent.click(screen.getByRole('button', { name: 'Parolni ko‘rsatish' }))
    expect(password).toHaveAttribute('type', 'text')
  })

  it('shows assistant modes and can load the latest saved translation', () => {
    window.localStorage.setItem('linguaai-token', JSON.stringify('test-token'))
    window.localStorage.setItem('linguaai-user', JSON.stringify({
      id: 7,
      nickname: 'Gulasal',
      is_active: true,
      created_at: '2026-10-14T00:00:00',
    }))
    window.localStorage.setItem('linguaai-latest-translation', JSON.stringify({
      text: 'Salom',
      translated_text: 'Hello',
      source_lang: 'uz',
      target_lang: 'en',
      style: 'Oddiy',
    }))

    render(<App />)
    expect(screen.getByRole('button', { name: 'Salom, Gulasal!' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: 'AI yordamchi' }))
    expect(screen.getByRole('button', { name: "So'zma-so'z va Grammatik tahlil" })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Oxirgi tarjimani yuklash' })).toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })
})

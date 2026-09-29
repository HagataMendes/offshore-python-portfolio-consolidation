import { useState, type ReactNode } from 'react'
import type { ClientId } from '../types'
import { ClientContext } from './clientContext'

/** Guarda qual cliente está selecionado para todas as telas. */
export function ClientProvider({ children }: { children: ReactNode }) {
  const [clientId, setClientId] = useState<ClientId>('maria')
  return <ClientContext.Provider value={{ clientId, setClientId }}>{children}</ClientContext.Provider>
}

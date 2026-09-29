import { createContext, useContext } from 'react'
import type { ClientId } from '../types'

export interface ClientContextValue {
  clientId: ClientId
  setClientId: (id: ClientId) => void
}

export const ClientContext = createContext<ClientContextValue | null>(null)

/** Devolve o cliente selecionado (Maria ou Manoel) e a função para trocar. */
export function useSelectedClient() {
  const ctx = useContext(ClientContext)
  if (!ctx) throw new Error('useSelectedClient precisa estar dentro de <ClientProvider>')
  return ctx
}

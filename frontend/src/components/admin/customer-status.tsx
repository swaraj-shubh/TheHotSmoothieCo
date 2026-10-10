"use client"

import { useState, useTransition } from "react"
import { toast } from "sonner"

import { setCustomerActive } from "@/app/actions/admin"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export function CustomerStatus({ userId, isActive }: { userId: string; isActive: boolean }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [pending, start] = useTransition()
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={isActive ? "destructive" : "outline"}>{isActive ? "Deactivate account" : "Reactivate account"}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isActive ? "Deactivate this customer?" : "Reactivate this customer?"}</DialogTitle>
          <DialogDescription>
            {isActive ? "They're signed out on every device and can't log in until reactivated. Orders are kept." : "They can sign in again."}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            start(async () => {
              const r = await setCustomerActive(userId, !isActive, reason)
              if (r.ok) {
                toast.success(r.message)
                setOpen(false)
              } else toast.error(r.error)
            })
          }}
        >
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (kept in the audit log)" minLength={3} required />
          <Button type="submit" variant={isActive ? "destructive" : "default"} disabled={pending}>
            Confirm
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}

"use client"

import type { ComponentProps, ReactNode } from "react"
import { useTransition } from "react"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

type Result = { ok: boolean; error?: string; message?: string }

/** Runs a Server Action with toast feedback; with `confirm`, asks first (destructive operations). */
export function ActionButton({
  run,
  confirm,
  children,
  ...props
}: Omit<ComponentProps<typeof Button>, "onClick"> & {
  run: () => Promise<Result>
  confirm?: { title: string; description?: ReactNode; action?: string }
}) {
  const [pending, start] = useTransition()
  const go = () =>
    start(async () => {
      const r = await run()
      if (r.ok) toast.success(r.message ?? "Done")
      else toast.error(r.error ?? "Something went wrong")
    })

  if (!confirm) {
    return (
      <Button {...props} disabled={pending || props.disabled} onClick={go}>
        {children}
      </Button>
    )
  }
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button {...props} disabled={pending || props.disabled}>
          {children}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{confirm.title}</AlertDialogTitle>
          {confirm.description && <AlertDialogDescription>{confirm.description}</AlertDialogDescription>}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={go}>{confirm.action ?? "Confirm"}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

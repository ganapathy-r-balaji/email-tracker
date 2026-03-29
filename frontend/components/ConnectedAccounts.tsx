"use client";

/**
 * ConnectedAccounts.tsx – Panel showing all connected Gmail accounts.
 *
 * Features:
 *   - Lists each account with email address + "Connected" timestamp
 *   - Disconnect button per row (disabled with tooltip if it's the last account)
 *   - "+ Add Gmail Account" button to start the add-account OAuth flow
 *   - Collapsible (open by default)
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Mail, Trash2, PlusCircle, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { accountsApi, type GmailAccount } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Props {
  accounts: GmailAccount[];
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

export function ConnectedAccounts({ accounts, onError, onSuccess }: Props) {
  const [open, setOpen] = useState(true);
  const queryClient = useQueryClient();

  const removeMutation = useMutation({
    mutationFn: accountsApi.remove,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      onSuccess(`${data.gmail_email} disconnected.`);
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to disconnect account.";
      onError(msg);
    },
  });

  const isOnlyAccount = accounts.length <= 1;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Header row */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3
                   hover:bg-slate-800/60 transition-colors text-left"
      >
        <span className="text-sm font-medium text-slate-200 flex items-center gap-2">
          <Mail className="w-4 h-4 text-blue-400" />
          Connected Gmail Accounts
          <span className="ml-1 text-xs bg-slate-700 text-slate-300 rounded-full px-2 py-0.5">
            {accounts.length}
          </span>
        </span>
        {open ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {/* Account list */}
      {open && (
        <div className="divide-y divide-slate-800">
          {accounts.map((account) => {
            const isRemoving = removeMutation.isPending && removeMutation.variables === account.id;
            const connectedDate = new Date(account.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
            });

            return (
              <div
                key={account.id}
                className="flex items-center justify-between px-4 py-3 gap-3"
              >
                {/* Email + date */}
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                    <Mail className="w-4 h-4 text-blue-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-slate-200 font-medium truncate">
                      {account.gmail_email}
                    </p>
                    <p className="text-xs text-slate-500">Connected {connectedDate}</p>
                  </div>
                </div>

                {/* Disconnect button */}
                <div className="relative group flex-shrink-0">
                  <button
                    onClick={() => removeMutation.mutate(account.id)}
                    disabled={isOnlyAccount || isRemoving}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs
                               text-red-400 border border-red-900/40 hover:bg-red-900/20
                               disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {isRemoving ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                    Disconnect
                  </button>
                  {/* Tooltip when only account */}
                  {isOnlyAccount && (
                    <div className="absolute bottom-full right-0 mb-2 hidden group-hover:block z-20">
                      <div className="bg-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5
                                      whitespace-nowrap shadow-lg border border-slate-600">
                        Add another account before disconnecting
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Add account button */}
          <div className="px-4 py-3">
            <button
              onClick={() => {
                window.location.href = `${API_URL}/auth/google?action=add`;
              }}
              className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300
                         transition-colors font-medium"
            >
              <PlusCircle className="w-4 h-4" />
              Add Gmail Account
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

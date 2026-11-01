import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export type Role = "Accountant" | "Finance Manager" | "Admin" | "Staff" | null;

export interface RoleInfo {
  role: Role;
  is_accountant: boolean;
  is_finance_manager: boolean;
  is_superuser: boolean;
  username: string;
}

export function useRole() {
  return useQuery<RoleInfo>({
    queryKey: ["auth-role"],
    queryFn: async () => (await api.get("/auth/role/")).data,
    staleTime: 5 * 60 * 1000,
  });
}

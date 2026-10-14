import { useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../../api/client";

export type TicketStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
export type TicketPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export type SortKey =
  | "ticket_number"
  | "title"
  | "priority"
  | "status"
  | "department_name"
  | "requested_by_username"
  | "assigned_to_username"
  | "location"
  | "created_at"
  | "updated_at"
  | "resolved_at";

type SortDirection = "asc" | "desc";

export interface TicketItem {
  id: number;
  ticket_number: string;
  title: string;
  description: string;
  priority: TicketPriority;
  status: TicketStatus;
  department_name: string | null;
  requested_by_username: string | null;
  assigned_to_username: string | null;
  location: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

interface ItTicketsSectionProps {
  userRole?: string;
  currentUserId?: number;
  currentUserUsername?: string;
  tickets: TicketItem[];
  loadingTickets: boolean;
  ticketsError: string;
  onTicketUpdated?: (ticket: TicketItem) => void;
}

const statusBadgeClass: Record<TicketStatus, string> = {
  OPEN: "bg-[var(--input-background)] text-[var(--foreground)] border border-[var(--border)]",
  IN_PROGRESS: "bg-amber-50 text-amber-700 border border-amber-200",
  RESOLVED: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  CLOSED: "bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]",
};

const priorityBadgeClass: Record<TicketPriority, string> = {
  LOW: "bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]",
  MEDIUM: "bg-[var(--input-background)] text-[var(--foreground)] border border-[var(--border)]",
  HIGH: "bg-orange-50 text-orange-700 border border-orange-200",
  URGENT: "bg-rose-50 text-rose-700 border border-rose-200",
};

const priorityDotClass: Record<TicketPriority, string> = {
  LOW: "bg-[var(--low-priority-tickets-icon)]",
  MEDIUM: "bg-[var(--normal-priority-tickets-icon)]",
  HIGH: "bg-[var(--high-priority-tickets-icon)]",
  URGENT: "bg-[var(--urgent-priority-tickets-icon)]",
};

const formatDateTime = (value: string | null): string => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";
  return parsed.toLocaleString();
};

const formatDateOnly = (value: string | null): string => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";

  const day = String(parsed.getDate()).padStart(2, "0");
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const year = parsed.getFullYear();
  return `${day}/${month}/${year}`;
};

const normalizeValue = (value: string | null | undefined): string => (value ?? "").toLowerCase();

const ItTicketsSection = ({
  userRole,
  currentUserId,
  currentUserUsername,
  tickets,
  loadingTickets,
  ticketsError,
  onTicketUpdated,
}: ItTicketsSectionProps) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | TicketStatus>("ALL");
  const [priorityFilter, setPriorityFilter] = useState<"ALL" | TicketPriority>("ALL");
  const [departmentFilter, setDepartmentFilter] = useState("ALL");
  const [assigneeFilter, setAssigneeFilter] = useState("ALL");
  const [requesterFilter, setRequesterFilter] = useState("ALL");
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState<TicketItem | null>(null);
  const [isUpdatingTicket, setIsUpdatingTicket] = useState(false);
  const [ticketUpdateError, setTicketUpdateError] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [currentPage, setCurrentPage] = useState(1);
  const ticketsPerPage = 10;

  const closeTicketDetails = () => {
    setSelectedTicket(null);
    setTicketUpdateError("");
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }

      if (selectedTicket) {
        closeTicketDetails();
        return;
      }

      if (isFilterModalOpen) {
        setIsFilterModalOpen(false);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isFilterModalOpen, selectedTicket]);

  const roleScopedTickets = useMemo(() => {
    const ceoRestricted = userRole === "CEO";
    return tickets.filter((ticket) => {
      if (ceoRestricted && !(ticket.priority === "HIGH" || ticket.priority === "URGENT")) {
        return false;
      }
      return true;
    });
  }, [tickets, userRole]);

  const visibleTickets = useMemo(() => {
    return roleScopedTickets.filter((ticket) => {
      if (statusFilter !== "ALL" && ticket.status !== statusFilter) {
        return false;
      }

      if (priorityFilter !== "ALL" && ticket.priority !== priorityFilter) {
        return false;
      }

      if (departmentFilter !== "ALL" && (ticket.department_name ?? "Unassigned") !== departmentFilter) {
        return false;
      }

      if (assigneeFilter !== "ALL" && (ticket.assigned_to_username ?? "Unassigned") !== assigneeFilter) {
        return false;
      }

      if (requesterFilter !== "ALL" && (ticket.requested_by_username ?? "Unknown") !== requesterFilter) {
        return false;
      }

      if (!searchTerm.trim()) {
        return true;
      }

      const query = searchTerm.trim().toLowerCase();
      return (
        normalizeValue(ticket.ticket_number).includes(query) ||
        normalizeValue(ticket.title).includes(query) ||
        normalizeValue(ticket.description).includes(query) ||
        normalizeValue(ticket.department_name).includes(query) ||
        normalizeValue(ticket.requested_by_username).includes(query) ||
        normalizeValue(ticket.assigned_to_username).includes(query) ||
        normalizeValue(ticket.location).includes(query)
      );
    });
  }, [
    roleScopedTickets,
    statusFilter,
    priorityFilter,
    departmentFilter,
    assigneeFilter,
    requesterFilter,
    searchTerm,
  ]);

  const sortedTickets = useMemo(() => {
    const priorityOrder: Record<TicketPriority, number> = { LOW: 1, MEDIUM: 2, HIGH: 3, URGENT: 4 };
    const statusOrder: Record<TicketStatus, number> = { OPEN: 1, IN_PROGRESS: 2, RESOLVED: 3, CLOSED: 4 };

    const sorted = [...visibleTickets].sort((a, b) => {
      let left: string | number = "";
      let right: string | number = "";

      if (sortKey === "priority") {
        left = priorityOrder[a.priority];
        right = priorityOrder[b.priority];
      } else if (sortKey === "status") {
        left = statusOrder[a.status];
        right = statusOrder[b.status];
      } else if (sortKey === "created_at" || sortKey === "updated_at" || sortKey === "resolved_at") {
        left = a[sortKey] ? new Date(a[sortKey]).getTime() : 0;
        right = b[sortKey] ? new Date(b[sortKey]).getTime() : 0;
      } else {
        left = normalizeValue(a[sortKey]);
        right = normalizeValue(b[sortKey]);
      }

      if (left < right) {
        return sortDirection === "asc" ? -1 : 1;
      }
      if (left > right) {
        return sortDirection === "asc" ? 1 : -1;
      }
      return 0;
    });

    return sorted;
  }, [visibleTickets, sortKey, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(sortedTickets.length / ticketsPerPage));

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const paginatedTickets = useMemo(() => {
    const startIndex = (currentPage - 1) * ticketsPerPage;
    return sortedTickets.slice(startIndex, startIndex + ticketsPerPage);
  }, [currentPage, sortedTickets]);

  const departmentOptions = useMemo(() => {
    const values = new Set(roleScopedTickets.map((t) => t.department_name ?? "Unassigned"));
    return ["ALL", ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [roleScopedTickets]);

  const assigneeOptions = useMemo(() => {
    const values = new Set(roleScopedTickets.map((t) => t.assigned_to_username ?? "Unassigned"));
    return ["ALL", ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [roleScopedTickets]);

  const requesterOptions = useMemo(() => {
    const values = new Set(roleScopedTickets.map((t) => t.requested_by_username ?? "Unknown"));
    return ["ALL", ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [roleScopedTickets]);

  const resetFilters = () => {
    setSearchTerm("");
    setStatusFilter("ALL");
    setPriorityFilter("ALL");
    setDepartmentFilter("ALL");
    setAssigneeFilter("ALL");
    setRequesterFilter("ALL");
    setCurrentPage(1);
  };

  const updateTicketStatus = async (nextStatus: "IN_PROGRESS" | "RESOLVED") => {
    if (!selectedTicket || isUpdatingTicket) {
      return;
    }

    try {
      setIsUpdatingTicket(true);
      setTicketUpdateError("");

      const payload: Record<string, number | string> = { status: nextStatus };

      if (nextStatus === "IN_PROGRESS") {
        if (typeof currentUserId !== "number") {
          throw new Error("Missing technician id.");
        }

        payload.assigned_to = currentUserId;
      }

      const responseData = await api.patch<{ status?: TicketStatus; resolved_at?: string | null }>(
        `/api/tickets/${selectedTicket.id}/`,
        payload,
      );

      const updatedTicket: TicketItem = {
        ...selectedTicket,
        status: responseData.status ?? nextStatus,
        resolved_at: responseData.resolved_at ?? selectedTicket.resolved_at,
        assigned_to_username:
          nextStatus === "IN_PROGRESS"
            ? currentUserUsername ?? selectedTicket.assigned_to_username
            : selectedTicket.assigned_to_username,
      };

      setSelectedTicket(updatedTicket);
      onTicketUpdated?.(updatedTicket);
    } catch (error) {
      console.error("Failed to update ticket:", error);
      setTicketUpdateError(errorMessage(error, "Could not update the ticket status."));
    } finally {
      setIsUpdatingTicket(false);
    }
  };

  const canManageTicket = userRole === "IT" && typeof currentUserId === "number";

  return (
    <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
      <div className="flex flex-col gap-1 mb-4">
        <h2 className="text-[1.05rem] font-semibold tracking-tight">Tickets</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          {userRole === "CEO"
            ? "CEO view: only HIGH and URGENT priority tickets are shown."
            : "IT view: all tickets are shown."}
        </p>
      </div>

      <div className="flex flex-col md:flex-row md:items-center gap-2 mb-4 flex-wrap">
        <button
          type="button"
          onClick={() => setIsFilterModalOpen(true)}
          className="cursor-pointer border border-[var(--border)] bg-[var(--card)] rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-[var(--input-background)] transition-colors"
        >
          Open Filters
        </button>

        <button
          type="button"
          onClick={resetFilters}
          className="cursor-pointer border border-[var(--border)] bg-[var(--card)] rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-[var(--input-background)] transition-colors"
        >
          Clear Filters
        </button>

        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="border border-[var(--border)] rounded-lg px-3 py-1.5 text-sm bg-[var(--input-background)]"
        >
          <option value="ticket_number">Sort by Ticket Number</option>
          <option value="title">Sort by Title</option>
          <option value="priority">Sort by Priority</option>
          <option value="status">Sort by Status</option>
          <option value="department_name">Sort by Department</option>
          <option value="requested_by_username">Sort by Requested By</option>
          <option value="assigned_to_username">Sort by Assigned To</option>
          <option value="location">Sort by Location</option>
          <option value="created_at">Sort by Created At</option>
          <option value="updated_at">Sort by Updated At</option>
          <option value="resolved_at">Sort by Resolved At</option>
        </select>

        <select
          value={sortDirection}
          onChange={(e) => setSortDirection(e.target.value as SortDirection)}
          className="border border-[var(--border)] rounded-lg px-3 py-1.5 text-sm bg-[var(--input-background)]"
        >
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </select>

        <div className="text-sm text-[var(--muted-foreground)] ml-auto">
          {searchTerm.trim() ? `Search: "${searchTerm}"` : "No search query"}
        </div>
      </div>

      <div className="mb-3 text-sm text-[var(--muted-foreground)]">
        Showing {sortedTickets.length} tickets
      </div>

      {isFilterModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setIsFilterModalOpen(false);
            }
          }}
        >
          <div className="w-full max-w-3xl bg-[var(--card)] border border-[var(--border)] rounded-2xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
              <h3 className="text-[1rem] font-semibold tracking-tight">Filter Tickets</h3>
              <button
                type="button"
                onClick={() => setIsFilterModalOpen(false)}
                className="cursor-pointer rounded-lg px-2 py-1 text-sm text-[var(--muted-foreground)] hover:bg-[var(--input-background)] hover:text-[var(--foreground)] transition-colors"
              >
                Close
              </button>
            </div>

            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Search</label>
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1);
                  }}
                  placeholder="Search ticket no, title, description, users, location"
                  className="w-full border border-[var(--border)] bg-[var(--input-background)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
                />
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value as "ALL" | TicketStatus);
                    setCurrentPage(1);
                  }}
                  className="w-full border border-[var(--border)] bg-[var(--input-background)] rounded-lg px-3 py-2 text-sm"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="OPEN">NEW</option>
                  <option value="IN_PROGRESS">IN_PROGRESS</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="CLOSED">CLOSED</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Priority</label>
                <select
                  value={priorityFilter}
                  onChange={(e) => {
                    setPriorityFilter(e.target.value as "ALL" | TicketPriority);
                    setCurrentPage(1);
                  }}
                  className="w-full border border-[var(--border)] bg-[var(--input-background)] rounded-lg px-3 py-2 text-sm"
                >
                  <option value="ALL">All Priorities</option>
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="URGENT">URGENT</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Department</label>
                <select
                  value={departmentFilter}
                  onChange={(e) => {
                    setDepartmentFilter(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full border border-[var(--border)] bg-[var(--input-background)] rounded-lg px-3 py-2 text-sm"
                >
                  {departmentOptions.map((option) => (
                    <option key={option} value={option}>
                      {option === "ALL" ? "All Departments" : option}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Assignee</label>
                <select
                  value={assigneeFilter}
                  onChange={(e) => {
                    setAssigneeFilter(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full border border-[var(--border)] bg-[var(--input-background)] rounded-lg px-3 py-2 text-sm"
                >
                  {assigneeOptions.map((option) => (
                    <option key={option} value={option}>
                      {option === "ALL" ? "All Assignees" : option}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Requester</label>
                <select
                  value={requesterFilter}
                  onChange={(e) => {
                    setRequesterFilter(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full border border-[var(--border)] bg-[var(--input-background)] rounded-lg px-3 py-2 text-sm"
                >
                  {requesterOptions.map((option) => (
                    <option key={option} value={option}>
                      {option === "ALL" ? "All Requesters" : option}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-[var(--border)]">
              <button
                type="button"
                onClick={resetFilters}
                className="cursor-pointer border border-[var(--border)] bg-[var(--card)] rounded-lg px-3.5 py-2 text-sm font-medium hover:bg-[var(--input-background)] transition-colors"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={() => setIsFilterModalOpen(false)}
                className="cursor-pointer bg-[var(--primary)] text-[var(--primary-foreground)] rounded-lg px-3.5 py-2 text-sm font-semibold hover:opacity-90 transition-opacity"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {ticketsError ? (
        <div className="text-sm text-[var(--destructive)] bg-rose-50 border border-rose-200 rounded-lg p-3">{ticketsError}</div>
      ) : loadingTickets ? (
        <div className="text-sm text-[var(--muted-foreground)]">Loading tickets...</div>
      ) : (
        <div className="overflow-x-auto border border-[var(--border)] rounded-xl">
          <table className="min-w-full bg-[var(--card)] text-sm">
            <thead className="bg-[var(--input-background)]">
              <tr>
                {['Ticket Number', 'Title', 'Requested By', 'Priority', 'Status', 'Created', 'Actions'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginatedTickets.map((ticket) => (
                <tr key={ticket.id} className="border-t border-[var(--border)] hover:bg-[var(--input-background)] transition-colors">
                  <td className="px-4 py-2.5 font-medium text-[var(--muted-foreground)] whitespace-nowrap">{ticket.ticket_number}</td>
                  <td className="px-4 py-2.5 min-w-[14rem] font-medium">{ticket.title}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">{ticket.requested_by_username ?? "Unknown"}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <div className="inline-flex items-center gap-2 text-sm font-medium">
                      <span className={`h-1.5 w-1.5 rounded-full ${priorityDotClass[ticket.priority]}`} />
                      <span className="capitalize">{ticket.priority.toLowerCase()}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${statusBadgeClass[ticket.status]}`}>
                      {ticket.status.toLowerCase().replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--muted-foreground)] whitespace-nowrap">{formatDateOnly(ticket.created_at)}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => setSelectedTicket(ticket)}
                      className="cursor-pointer border border-[var(--border)] bg-[var(--card)] rounded-lg px-3 py-1 text-xs font-medium hover:bg-[var(--input-background)] transition-colors"
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {sortedTickets.length === 0 && (
            <div className="p-4 text-sm text-[var(--muted-foreground)]">No tickets match the current filters.</div>
          )}
        </div>
      )}

      {!ticketsError && !loadingTickets && sortedTickets.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-4 text-sm text-[var(--muted-foreground)]">
          <div>
            Showing {(currentPage - 1) * ticketsPerPage + 1}-{Math.min(currentPage * ticketsPerPage, sortedTickets.length)} of {sortedTickets.length} tickets
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
              disabled={currentPage === 1}
              className="cursor-pointer border border-[var(--border)] bg-[var(--card)] rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-[var(--input-background)] transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>

            <span className="min-w-[6rem] text-center">
              Page {currentPage} of {totalPages}
            </span>

            <button
              type="button"
              onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
              disabled={currentPage === totalPages}
              className="cursor-pointer border border-[var(--border)] bg-[var(--card)] rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-[var(--input-background)] transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {selectedTicket && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeTicketDetails();
            }
          }}
        >
          <div className="w-full max-w-2xl bg-[var(--card)] border border-[var(--border)] rounded-2xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
              <h3 className="text-[1rem] font-semibold tracking-tight">
                Ticket Details · {selectedTicket.ticket_number}
              </h3>
              <button
                type="button"
                onClick={closeTicketDetails}
                className="cursor-pointer rounded-lg px-2 py-1 text-sm text-[var(--muted-foreground)] hover:bg-[var(--input-background)] hover:text-[var(--foreground)] transition-colors"
              >
                Close
              </button>
            </div>

            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Title</div>
                <div>{selectedTicket.title}</div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Department</div>
                <div>{selectedTicket.department_name ?? "Unassigned"}</div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Requested By</div>
                <div>{selectedTicket.requested_by_username ?? "Unknown"}</div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Assigned To</div>
                <div>{selectedTicket.assigned_to_username ?? "Unassigned"}</div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Priority</div>
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${priorityBadgeClass[selectedTicket.priority]}`}>
                  {selectedTicket.priority}
                </span>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Status</div>
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusBadgeClass[selectedTicket.status]}`}>
                  {selectedTicket.status}
                </span>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Location</div>
                <div>{selectedTicket.location || "-"}</div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Created At</div>
                <div>{formatDateTime(selectedTicket.created_at)}</div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Updated At</div>
                <div>{formatDateTime(selectedTicket.updated_at)}</div>
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Resolved At</div>
                <div>{formatDateTime(selectedTicket.resolved_at)}</div>
              </div>

              <div className="md:col-span-2">
                <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Description</div>
                <div className="whitespace-pre-wrap">{selectedTicket.description || "-"}</div>
              </div>

              {ticketUpdateError && (
                <div className="md:col-span-2 text-sm text-[var(--destructive)] bg-rose-50 border border-rose-200 rounded-lg p-3">
                  {ticketUpdateError}
                </div>
              )}
            </div>

            <div className="flex flex-col-reverse sm:flex-row sm:items-center justify-end gap-3 px-5 py-4 border-t border-[var(--border)]">
              <button
                type="button"
                onClick={closeTicketDetails}
                className="cursor-pointer border border-[var(--border)] bg-[var(--card)] rounded-lg px-3.5 py-2 text-sm font-medium hover:bg-[var(--input-background)] transition-colors"
              >
                Close
              </button>

              {canManageTicket && selectedTicket.status === "OPEN" && (
                <button
                  type="button"
                  onClick={() => updateTicketStatus("IN_PROGRESS")}
                  disabled={isUpdatingTicket}
                  className="cursor-pointer bg-[var(--primary)] text-[var(--primary-foreground)] rounded-lg px-3.5 py-2 text-sm font-semibold hover:opacity-90 transition-opacity disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isUpdatingTicket ? "Accepting..." : "Accept"}
                </button>
              )}

              {canManageTicket && selectedTicket.status === "IN_PROGRESS" && (
                <button
                  type="button"
                  onClick={() => updateTicketStatus("RESOLVED")}
                  disabled={isUpdatingTicket}
                  className="cursor-pointer bg-[var(--primary)] text-[var(--primary-foreground)] rounded-lg px-3.5 py-2 text-sm font-semibold hover:opacity-90 transition-opacity disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isUpdatingTicket ? "Resolving..." : "Resolve"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default ItTicketsSection;

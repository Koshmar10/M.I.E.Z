import { useEffect, useState } from "react";
import { api, type Page } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import ItTicketsSection, { type TicketItem } from "./ItTicketsSection";
import StatCard from "./StatsCard";
import { LuTicket } from "react-icons/lu";
import { IoSunnyOutline } from "react-icons/io5";
import { IoMdCheckmarkCircleOutline } from "react-icons/io";

type AssignedTicketsPage = Page<TicketItem> & {
  technician_summary?: { assigned_count: number; in_progress_count: number; resolved_count: number };
};

const ItAssignedPage = () => {
  const { user } = useAuth();
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [loadingTickets, setLoadingTickets] = useState(true);
  const [ticketsError, setTicketsError] = useState("");
  const [assignedCount, setAssignedCount] = useState<number | null>(null);
  const [inProgressCount, setInProgressCount] = useState<number | null>(null);
  const [resolvedCount, setResolvedCount] = useState<number | null>(null);

  useEffect(() => {
    const fetchAssigned = async () => {
      try {
        setLoadingTickets(true);
        setTicketsError("");

        let nextUrl: string | null = "/api/tickets/?assigned_to=me&page_size=10";
        const all: TicketItem[] = [];
        let first = true;

        while (nextUrl) {
          const data: AssignedTicketsPage = await api.get<AssignedTicketsPage>(nextUrl);

          if (first) {
            first = false;
            const ts = data.technician_summary;
            if (ts) {
              setAssignedCount(ts.assigned_count);
              setInProgressCount(ts.in_progress_count);
              setResolvedCount(ts.resolved_count);
            }
          }

          all.push(...data.results);
          nextUrl = data.next;
        }

        setTickets(all);
      } catch (err) {
        console.error(err);
        setTicketsError("Could not load assigned tickets.");
      } finally {
        setLoadingTickets(false);
      }
    };

    fetchAssigned();
  }, []);

  return (
    <div className="w-full lg:w-[92%] mx-auto space-y-6">
      <section className="bg-white border border-gray-200 rounded-lg p-4 md:p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Assigned Tickets</h2>
            <p className="text-sm text-gray-500">Technician: {user?.username ?? 'You'}</p>
          </div>
          <div className="text-sm text-gray-700">Total assigned: {assignedCount ?? '—'}</div>
        </div>

        <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatCard title="In Progress" value={inProgressCount ?? 0} icon={IoSunnyOutline} iconColor="in-progress-tickets-text" />
          <StatCard title="Assigned" value={assignedCount ?? 0} icon={LuTicket} iconColor="open-tickets-icon" />
          <StatCard title="Resolved" value={resolvedCount ?? 0} icon={IoMdCheckmarkCircleOutline} iconColor="chart-2" />
        </div>
      </section>

      <ItTicketsSection
        userRole={user?.role}
        currentUserId={user?.id}
        currentUserUsername={user?.username}
        tickets={tickets}
        loadingTickets={loadingTickets}
        ticketsError={ticketsError}
        onTicketUpdated={(updatedTicket) => {
          setTickets((prev) => prev.map((ticket) => (ticket.id === updatedTicket.id ? updatedTicket : ticket)));
        }}
      />
    </div>
  );
};

export default ItAssignedPage;

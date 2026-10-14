import type { IconType } from "react-icons";
import StatsCard from "./StatsCard";
import ItTicketTrendChart from "./ItTicketTrendChart";
import ItTicketsSection from "./ItTicketsSection";
import SystemStatusPanel from "../common/SystemStatusPanel";
import { LuTicket } from "react-icons/lu";
import { IoSunnyOutline } from "react-icons/io5";
import { IoMdCheckmarkCircleOutline } from "react-icons/io";
import { MdAccessTime } from "react-icons/md";
import { FiAlertTriangle } from "react-icons/fi";
import { useEffect, useMemo, useState } from "react";
import { api, type Page } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useNavigate } from "react-router-dom";

interface ItStatsResponse {
  open_ticket: number;
  in_progress: number;
  resolved_this_week: number;
  ceo_it_summary: {
    avg_resolution_time_hrs: number;
    sla_met_percentage: number;
    critical_open_tickets?: number;
    critical_open?: number;
  };
}

interface TicketTrendWeek {
  week_start: string;
  opened_count: number;
  closed_count: number;
}

interface TechnicianStat {
  user_id: number;
  username: string;
  resolved_count: number;
  avg_resolution_hours: number;
  sla_percent: number;
}

type AssetStatus = "AVAILABLE" | "ASSIGNED" | "MAINTENANCE" | "RETIRED";

interface AssetItem {
  id: number;
  name: string;
  status: AssetStatus;
  created_at: string;
}

interface AssetSummary {
  total: number;
  available: number;
  assigned: number;
  maintenance: number;
  retired: number;
  recent: AssetItem[];
}

type TechnicianWindow = 7 | 30 | 90;

type TicketStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
type TicketPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

interface TicketItem {
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

interface StatConfig {
  title: string;
  icon: IconType;
  iconColor: string;
  getValue: (stats: ItStatsResponse) => number;
  suffix?: string;
}

const ItDashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<ItStatsResponse | null>(null);
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [ticketTrend, setTicketTrend] = useState<TicketTrendWeek[]>([]);
  const [technicianStats, setTechnicianStats] = useState<TechnicianStat[]>([]);
  const [assetSummary, setAssetSummary] = useState<AssetSummary>({
    total: 0,
    available: 0,
    assigned: 0,
    maintenance: 0,
    retired: 0,
    recent: [],
  });
  const [loadingAssetSummary, setLoadingAssetSummary] = useState(false);
  const [assetSummaryError, setAssetSummaryError] = useState<string>("");
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingTickets, setLoadingTickets] = useState(true);
  const [loadingTrend, setLoadingTrend] = useState(false);
  const [loadingTechnicianStats, setLoadingTechnicianStats] = useState(false);
  const [ticketsError, setTicketsError] = useState<string>("");
  const [trendError, setTrendError] = useState<string>("");
  const [technicianStatsError, setTechnicianStatsError] = useState<string>("");
  const [technicianWindow, setTechnicianWindow] = useState<TechnicianWindow>(30);

  const cardsConfig: StatConfig[] = useMemo(() => {
    if (user?.role === "CEO") {
      return [
        {title: "Open Tickets", icon: LuTicket, iconColor: "open-tickets-icon", getValue: (s) => s.open_ticket},
        {title: "Avg. Resolution Time", icon: MdAccessTime, iconColor: "open-tickets-icon", getValue: (s) => s.ceo_it_summary.avg_resolution_time_hrs, suffix: "hrs"},
        {title: "SLA Compliance", icon: IoMdCheckmarkCircleOutline, iconColor: "chart-2", getValue: (s) => s.ceo_it_summary.sla_met_percentage, suffix: "%"},
        {title: "Critical Open Tickets", icon: FiAlertTriangle, iconColor: "critical-tickets-icon", getValue: (s) => s.ceo_it_summary.critical_open ?? s.ceo_it_summary.critical_open_tickets ?? 0},
      ];
    }

    return [
      {title: "Open Tickets", icon: LuTicket, iconColor: "open-tickets-icon", getValue: (s) => s.open_ticket},
      {title: "In Progress", icon: IoSunnyOutline, iconColor: "open-tickets-icon", getValue: (s) => s.in_progress},
      {title: "Resolved This Week", icon: IoMdCheckmarkCircleOutline, iconColor: "chart-2", getValue: (s) => s.resolved_this_week}
    ];
  }, [user?.role]);

  useEffect(() => {
    api.get<ItStatsResponse>("/api/it/dashboard/")
    .then((data) => {
      setStats(data);
      setLoadingStats(false);
    })
    .catch((err: unknown) => {
      console.error("Error fetching IT dashboard stats:", err);
      setLoadingStats(false);
    });
  }, []);

  useEffect(() => {
    if (user?.role !== "CEO") {
      setLoadingTrend(false);
      setTicketTrend([]);
      return;
    }

    setLoadingTrend(true);
    api.get<{ weeks?: TicketTrendWeek[] }>("/api/it/ticket-trend/")
      .then((data) => {
        setTicketTrend(Array.isArray(data.weeks) ? data.weeks : []);
        setLoadingTrend(false);
      })
      .catch((err: unknown) => {
        console.error("Error fetching IT ticket trend:", err);
        setTrendError("Could not load ticket trend.");
        setLoadingTrend(false);
      });
  }, [user?.role]);

  useEffect(() => {
    const fetchAllTickets = async () => {
      try {
        setLoadingTickets(true);
        setTicketsError("");

        let nextUrl: string | null = "/api/tickets/?page_size=10";
        const allTickets: TicketItem[] = [];

        while (nextUrl) {
          const data: Page<TicketItem> = await api.get<Page<TicketItem>>(nextUrl);
          allTickets.push(...data.results);
          nextUrl = data.next;
        }

        setTickets(allTickets);
      } catch (err) {
        console.error("Error fetching tickets:", err);
        setTicketsError("Could not load tickets.");
      } finally {
        setLoadingTickets(false);
      }
    };

    void fetchAllTickets();
  }, []);

  useEffect(() => {
    if (user?.role !== "IT" && user?.role !== "CEO") {
      setTechnicianStats([]);
      setTechnicianStatsError("");
      setLoadingTechnicianStats(false);
      return;
    }

    const fetchTechnicianStats = async () => {
      try {
        setLoadingTechnicianStats(true);
        setTechnicianStatsError("");

        const data = await api.get<{ technicians?: TechnicianStat[] }>("/api/it/technician-stats/", { days: technicianWindow });
        setTechnicianStats(Array.isArray(data.technicians) ? data.technicians : []);
      } catch (error) {
        console.error("Error fetching technician stats:", error);
        setTechnicianStatsError("Could not load technician performance stats.");
      } finally {
        setLoadingTechnicianStats(false);
      }
    };

    void fetchTechnicianStats();
  }, [technicianWindow, user?.role]);

  useEffect(() => {
    if (user?.role !== "IT" && user?.role !== "CEO") {
      setAssetSummary({
        total: 0,
        available: 0,
        assigned: 0,
        maintenance: 0,
        retired: 0,
        recent: [],
      });
      setAssetSummaryError("");
      setLoadingAssetSummary(false);
      return;
    }

    const fetchAssetSummary = async () => {
      try {
        setLoadingAssetSummary(true);
        setAssetSummaryError("");

        const assets = await api.get<AssetItem[]>("/api/it/assets/");
        const recentAssets = [...assets]
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .slice(0, 5)
          .map((asset: AssetItem) => ({
            id: asset.id,
            name: asset.name,
            status: asset.status,
            created_at: asset.created_at,
          }));

        setAssetSummary({
          total: assets.length,
          available: assets.filter((asset) => asset.status === "AVAILABLE").length,
          assigned: assets.filter((asset) => asset.status === "ASSIGNED").length,
          maintenance: assets.filter((asset) => asset.status === "MAINTENANCE").length,
          retired: assets.filter((asset) => asset.status === "RETIRED").length,
          recent: recentAssets,
        });
      } catch (error) {
        console.error("Error fetching IT asset summary:", error);
        setAssetSummaryError("Could not load asset summary.");
      } finally {
        setLoadingAssetSummary(false);
      }
    };

    void fetchAssetSummary();
  }, [user?.role]);

  const technicianChartData = useMemo(() => {
    return [...technicianStats]
      .sort((a, b) => b.resolved_count - a.resolved_count || a.username.localeCompare(b.username))
      .map((technician) => ({
        name: technician.username,
        resolved: technician.resolved_count,
      }));
  }, [technicianStats]);

  const assetStatusTone = (status: AssetStatus) => {
    if (status === "AVAILABLE") return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (status === "ASSIGNED") return "bg-blue-50 text-blue-700 border-blue-200";
    if (status === "MAINTENANCE") return "bg-amber-50 text-amber-700 border-amber-200";
    return "bg-[var(--input-background)] text-[var(--muted-foreground)] border-[var(--border)]";
  };

  if (loadingStats) return <div className="p-6">Loading data...</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {cardsConfig.map((config, index) => (
          <StatsCard
            key={index}
            title={config.title}
            icon={config.icon}
            iconColor={config.iconColor}
            value={stats ? config.getValue(stats) : 0}
            suffix={config.suffix}
          />
        ))}
      </div>

      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-[1.05rem] font-semibold tracking-tight">Technician Performance</h2>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">
              Resolved tickets, average resolution time, and SLA compliance for the selected window.
            </p>
          </div>

          <div className="inline-flex rounded-lg border border-[var(--border)] bg-[var(--input-background)] p-1 w-fit">
            {([7, 30, 90] as TechnicianWindow[]).map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => setTechnicianWindow(days)}
                className={`cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  technicianWindow === days
                    ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                {days}d
              </button>
            ))}
          </div>
        </div>

        {loadingTechnicianStats ? (
          <p className="text-sm text-[var(--muted-foreground)]">Loading technician stats...</p>
        ) : technicianStatsError ? (
          <p className="text-sm text-[var(--destructive)]">{technicianStatsError}</p>
        ) : technicianStats.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">No resolved tickets were found in the selected window.</p>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="overflow-x-auto border border-[var(--border)] rounded-xl">
              <table className="min-w-full bg-[var(--card)] text-sm">
                <thead className="bg-[var(--input-background)]">
                  <tr>
                    {['Technician', 'Resolved', 'Avg. Resolution', 'SLA %'].map((heading) => (
                      <th
                        key={heading}
                        className="px-4 py-2.5 text-left text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {technicianStats.map((technician) => (
                    <tr key={technician.user_id} className="border-t border-[var(--border)] hover:bg-[var(--input-background)] transition-colors">
                      <td className="px-4 py-2.5 font-medium">{technician.username}</td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{technician.resolved_count}</td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{technician.avg_resolution_hours.toFixed(2)} hrs</td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{technician.sla_percent.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="border border-[var(--border)] rounded-xl p-4">
              <div className="flex items-center justify-between gap-2 mb-3">
                <h3 className="text-sm font-semibold tracking-tight">Resolved tickets by technician</h3>
                <span className="text-xs text-[var(--muted-foreground)]">Visual summary</span>
              </div>
              <div className="space-y-3">
                {technicianChartData.map((technician) => {
                  const maxResolved = Math.max(...technicianChartData.map((entry) => entry.resolved), 1);
                  const widthPercent = Math.max((technician.resolved / maxResolved) * 100, 6);

                  return (
                    <div key={technician.name} className="space-y-1.5">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="font-medium truncate">{technician.name}</span>
                        <span className="text-[var(--muted-foreground)]">{technician.resolved}</span>
                      </div>
                      <div className="h-2 rounded-full bg-[var(--input-background)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[var(--primary)]"
                          style={{ width: `${widthPercent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {user?.role === "CEO" && (
            <ItTicketTrendChart
              loading={loadingTrend}
              error={trendError}
              ticketTrend={ticketTrend}
            />
          )}

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

        <div className="space-y-6">
          <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[1.05rem] font-semibold tracking-tight">Assets</h2>
                <p className="text-sm text-[var(--muted-foreground)] mt-1">
                  Physical devices tracked in /it/assets.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void navigate("/it/assets")}
                className="rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm font-medium transition-colors hover:bg-[var(--card)]"
              >
                Open Assets
              </button>
            </div>

            {loadingAssetSummary ? (
              <p className="text-sm text-[var(--muted-foreground)]">Loading asset summary...</p>
            ) : assetSummaryError ? (
              <p className="text-sm text-[var(--destructive)]">{assetSummaryError}</p>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    ["Total", assetSummary.total],
                    ["Available", assetSummary.available],
                    ["Assigned", assetSummary.assigned],
                    ["Maintenance", assetSummary.maintenance],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="rounded-xl border border-[var(--border)] bg-[var(--input-background)] p-3">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{label}</p>
                      <p className="mt-1 text-lg font-semibold">{value as number}</p>
                    </div>
                  ))}
                </div>

                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Recent assets</p>
                  {assetSummary.recent.length === 0 ? (
                    <p className="mt-2 text-sm text-[var(--muted-foreground)]">No assets available yet.</p>
                  ) : (
                    <ul className="mt-2 space-y-2">
                      {assetSummary.recent.map((asset) => (
                        <li key={asset.id} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] px-3 py-2">
                          <span className="text-sm font-medium truncate">{asset.name}</span>
                          <span className={`inline-flex shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${assetStatusTone(asset.status)}`}>
                            {asset.status}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </>
            )}
          </section>

          {user?.role === "CEO" && <SystemStatusPanel />}
        </div>
      </div>
    </div>
  );
};

export default ItDashboard;

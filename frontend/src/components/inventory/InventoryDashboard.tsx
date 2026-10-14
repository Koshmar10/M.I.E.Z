import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import type { IconType } from "react-icons";
import { api, type Page } from "../../api/client";
import { FiX, FiPackage, FiBox, FiAlertTriangle, FiXCircle, FiTruck, FiRepeat, FiCheck, FiSearch, FiFilter, FiArrowRight } from "react-icons/fi";

// --- API DATA TYPES ---
interface DashboardKpis {
  total_products: number;
  low_stock_count: number;
  out_of_stock_count: number;
  deliveries_today: number;
}

interface ApiProduct {
  id: number;
  name: string;
  sku: string;
  category: string;
  stock_count: number;
  min_stock: number;
  unit_price_ron: number;
  status: 'OK' | 'LOW' | 'OUT';
  shortfall: number;
}

interface FlowData {
  nodes: { name: string; type?: string }[];
  links: { source: number; target: number; value: number; items: string; product_name?: string }[];
  date_range?: { start: string; end: string };
}

// --- LOGISTICS TRACE OVERVIEW ---
/** Units that moved between the warehouse and one supplier or destination. */
type PartnerTrace = { name: string; volume: number; details: string[] };
/** Where one product came from and went to. */
type ProductTrace = {
  name: string;
  inbound: { from: string; units: number }[];
  outbound: { to: string; units: number }[];
  totalIn: number;
  totalOut: number;
};

function TraceCard({ title, icon: Icon, accentText, items }: { title: string; icon: IconType; accentText: string; items: ReactNode[] }) {
  return (
    <div className="flex-1 bg-[var(--card)] rounded-2xl border border-[var(--border)] overflow-hidden flex flex-col max-h-[600px]">
      <div className="px-5 py-4 border-b border-[var(--border)] flex items-center gap-3 shrink-0 bg-[var(--input-background)]">
        <div className={`w-10 h-10 rounded-xl bg-[var(--card)] border border-[var(--border)] grid place-items-center ${accentText}`}>
          <Icon size={18} />
        </div>
        <div>
          <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]">{title}</h3>
          <p className="text-sm font-semibold mt-0.5">{items.length} active records</p>
        </div>
      </div>

      <div className="divide-y divide-[var(--border)] overflow-y-auto flex-1 slim-scroll">
        {items.length > 0 ? items : (
          <div className="text-sm text-[var(--muted-foreground)] py-8 text-center italic">No movement data available</div>
        )}
      </div>
    </div>
  );
}

function PartnerTraceItem({ trace, direction }: { trace: PartnerTrace; direction: 'in' | 'out' }) {
  const [accentText, accentBg] = direction === 'out' ? ['text-rose-700', 'bg-rose-50'] : ['text-emerald-700', 'bg-emerald-50'];
  return (
    <div className="p-4 hover:bg-[var(--input-background)] transition-colors">
      <div className="flex justify-between items-start mb-2.5 gap-3">
        <h4 className="text-sm font-semibold">{trace.name}</h4>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${accentBg} ${accentText} border border-current/20`}>
          {trace.volume.toLocaleString()} units
        </span>
      </div>
      <div className="bg-[var(--input-background)] rounded-lg p-2.5 border border-[var(--border)]">
        <p className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1.5">
          {direction === 'out' ? 'Items Sent' : 'Items Received'}
        </p>
        <ul className="space-y-1">
          {trace.details.map((detail, j) => (
            <li key={j} className="text-xs text-[var(--muted-foreground)] flex items-start gap-2">
              <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${direction === 'out' ? 'bg-rose-400' : 'bg-emerald-400'}`} />
              {detail}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ProductTraceItem({ trace }: { trace: ProductTrace }) {
  return (
    <div className="p-4 hover:bg-[var(--input-background)] transition-colors">
      <div className="flex justify-between items-start mb-2.5 gap-3">
        <h4 className="text-sm font-semibold">{trace.name}</h4>
        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] border border-current/20">
          {(trace.totalIn + trace.totalOut).toLocaleString()} moved
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-emerald-50 rounded-lg p-2 border border-emerald-200/60">
          <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-[0.14em] mb-1">In ({trace.totalIn})</p>
          {trace.inbound.length > 0 ? trace.inbound.map((entry, j) => (
            <p key={j} className="text-[11px] text-[var(--muted-foreground)] truncate" title={entry.from}>• {entry.from} ({entry.units})</p>
          )) : <p className="text-[11px] text-[var(--muted-foreground)] italic">None</p>}
        </div>
        <div className="bg-rose-50 rounded-lg p-2 border border-rose-200/60">
          <p className="text-[10px] font-semibold text-rose-700 uppercase tracking-[0.14em] mb-1">Out ({trace.totalOut})</p>
          {trace.outbound.length > 0 ? trace.outbound.map((entry, j) => (
            <p key={j} className="text-[11px] text-[var(--muted-foreground)] truncate" title={entry.to}>• {entry.to} ({entry.units})</p>
          )) : <p className="text-[11px] text-[var(--muted-foreground)] italic">None</p>}
        </div>
      </div>
    </div>
  );
}

function LogisticsOverview({ data }: { data: FlowData }) {
  const inbound = new Map<number, PartnerTrace>();
  const outbound = new Map<number, PartnerTrace>();
  const products = new Map<string, ProductTrace>(
    data.nodes
      .filter(n => n.type === 'product')
      .map(n => [n.name, { name: n.name, inbound: [], outbound: [], totalIn: 0, totalOut: 0 }]),
  );

  const traceFor = (traces: Map<number, PartnerTrace>, index: number, name: string) => {
    let trace = traces.get(index);
    if (!trace) {
      trace = { name, volume: 0, details: [] };
      traces.set(index, trace);
    }
    return trace;
  };

  for (const link of data.links) {
    const sourceNode = data.nodes.at(link.source);
    const targetNode = data.nodes.at(link.target);
    const product = link.product_name ? products.get(link.product_name) : undefined;

    // Supplier -> Product
    if (sourceNode?.type === 'supplier') {
      const trace = traceFor(inbound, link.source, sourceNode.name);
      trace.volume += link.value;
      trace.details.push(link.items || `${targetNode?.name ?? 'Items'} (${link.value})`);
      if (product) {
        product.inbound.push({ from: sourceNode.name, units: link.value });
        product.totalIn += link.value;
      }
    }

    // Warehouse -> Outbound
    if (targetNode?.type === 'out') {
      const trace = traceFor(outbound, link.target, targetNode.name);
      trace.volume += link.value;
      trace.details.push(link.items || `Items (${link.value})`);
      if (product) {
        product.outbound.push({ to: targetNode.name, units: link.value });
        product.totalOut += link.value;
      }
    }
  }

  const byVolume = (a: PartnerTrace, b: PartnerTrace) => b.volume - a.volume;
  const inboundList = [...inbound.values()].sort(byVolume);
  const outboundList = [...outbound.values()].sort(byVolume);
  const productList = [...products.values()]
    .filter(p => p.totalIn > 0 || p.totalOut > 0)
    .sort((a, b) => (b.totalIn + b.totalOut) - (a.totalIn + a.totalOut));

  return (
    <div className="relative">
      <style>{`
        .slim-scroll::-webkit-scrollbar {
          width: 6px;
        }
        .slim-scroll::-webkit-scrollbar-track {
          background: transparent;
        }
        .slim-scroll::-webkit-scrollbar-thumb {
          background-color: var(--border);
          border-radius: 20px;
        }
        .slim-scroll {
          scrollbar-width: thin;
          scrollbar-color: var(--border) transparent;
        }
      `}</style>
      <div className="flex flex-col lg:flex-row gap-4 h-[600px]">
        <TraceCard
          title="Suppliers Trace"
          icon={FiTruck}
          accentText="text-emerald-700"
          items={inboundList.map((trace, i) => <PartnerTraceItem key={i} trace={trace} direction="in" />)}
        />
        <TraceCard
          title="Product Trace"
          icon={FiPackage}
          accentText="text-[var(--primary)]"
          items={productList.map((trace, i) => <ProductTraceItem key={i} trace={trace} />)}
        />
        <TraceCard
          title="Destinations Trace"
          icon={FiArrowRight}
          accentText="text-rose-700"
          items={outboundList.map((trace, i) => <PartnerTraceItem key={i} trace={trace} direction="out" />)}
        />
      </div>
    </div>
  );
}

// --- UI COMPONENTS ---
const KPICard = ({ label, value, sub, icon: Icon }: { label: string; value: ReactNode; sub?: string; icon: IconType }) => (
  <article className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 flex items-start justify-between gap-3">
    <div className="flex flex-col">
      <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{label}</p>
      <p className="text-2xl font-semibold mt-1 tracking-tight">{value}</p>
      {sub && <p className="text-xs text-[var(--muted-foreground)] mt-1">{sub}</p>}
    </div>
    <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
      <Icon size={18} />
    </div>
  </article>
);

const STOCK_STATUS: Record<ApiProduct['status'], { label: string; style: string; icon: IconType }> = {
  OK: { label: 'Healthy', style: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: FiCheck },
  LOW: { label: 'Low Stock', style: 'bg-amber-50 text-amber-700 border-amber-200', icon: FiAlertTriangle },
  OUT: { label: 'Depleted', style: 'bg-rose-50 text-rose-700 border-rose-200', icon: FiXCircle },
};

const StatusBadge = ({ status }: { status: ApiProduct['status'] }) => {
  const { label, style, icon: Icon } = STOCK_STATUS[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${style}`}>
      <Icon size={12} />
      {label}
    </span>
  );
};

const DetailDrawer = ({ open, onClose, product }: { open: boolean, onClose: () => void, product: ApiProduct | null }) => {
  return (
    <>
      <div
        className={`fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />
      <div className={`fixed inset-y-0 right-0 w-full max-w-md bg-[var(--card)] border-l border-[var(--border)] z-50 transform transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col ${open ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="p-5 border-b border-[var(--border)] flex items-center justify-between sticky top-0 z-10 bg-[var(--card)]">
          <div>
            <h2 className="text-[1.05rem] font-semibold tracking-tight">{product?.name}</h2>
            <p className="text-sm text-[var(--muted-foreground)] flex items-center gap-2 mt-1">
              <span className="bg-[var(--input-background)] px-2 py-0.5 rounded text-xs font-mono">{product?.sku}</span>
              · {product?.category}
            </p>
          </div>
          <button onClick={onClose} className="p-2 bg-[var(--input-background)] hover:bg-[var(--border)] rounded-full text-[var(--muted-foreground)] transition-colors">
            <FiX size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {product && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--input-background)]">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium mb-1">Current Stock</p>
                  <p className="text-2xl font-semibold tracking-tight">{product.stock_count}</p>
                </div>
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--input-background)]">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium mb-1">Status</p>
                  <div className="mt-2"><StatusBadge status={product.status} /></div>
                </div>
              </div>

              <div className="space-y-2.5 py-4 border-t border-b border-[var(--border)]">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-[var(--muted-foreground)]">Minimum Threshold</span>
                  <span className="text-sm font-semibold">{product.min_stock} units</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-[var(--muted-foreground)]">Unit Price</span>
                  <span className="text-sm font-semibold">{(product.unit_price_ron || 0).toFixed(2)} RON</span>
                </div>
                {product.status !== 'OK' && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-[var(--muted-foreground)]">Shortfall</span>
                    <span className="text-sm font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full">{product.shortfall} units</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

// --- MAIN DASHBOARD COMPONENT ---
export default function InventoryDashboard() {
  const [selectedProduct, setSelectedProduct] = useState<ApiProduct | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [page, setPage] = useState(1);

  const kpisQuery = useQuery({
    queryKey: ['inventory', 'dashboard'],
    queryFn: () => api.get<DashboardKpis>('/api/inventory/dashboard/'),
  });
  const flowQuery = useQuery({
    queryKey: ['inventory', 'flow', 7],
    queryFn: () => api.get<FlowData>('/api/inventory/flow/', { days: 7 }),
  });
  const productsQuery = useQuery({
    queryKey: ['inventory', 'products', { search, category, statusFilter, page }],
    queryFn: () =>
      api.get<Page<ApiProduct>>('/api/inventory/products/', {
        search,
        category: category === 'All' ? undefined : category,
        status: statusFilter === 'All' ? undefined : statusFilter,
        page,
      }),
  });

  const kpis = kpisQuery.data;
  const loading = kpisQuery.isPending;
  const flowData = flowQuery.data;
  const products = productsQuery.data?.results ?? [];
  const totalProducts = productsQuery.data?.count ?? 0;
  const loadingProducts = productsQuery.isPending;

  return (
    <div className="space-y-6">

      {/* KPI GRID */}
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <header className="mb-4">
          <h2 className="text-[1.05rem] font-semibold tracking-tight">Inventory Dashboard</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">Real-time inventory metrics and forecasting.</p>
        </header>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <KPICard
            label="Total Products"
            value={loading ? "…" : (kpis?.total_products ?? 0)}
            sub="active SKUs"
            icon={FiBox}
          />
          <KPICard
            label="Low Stock Items"
            value={loading ? "…" : (kpis?.low_stock_count ?? 0)}
            sub="below threshold"
            icon={FiAlertTriangle}
          />
          <KPICard
            label="Out of Stock"
            value={loading ? "…" : (kpis?.out_of_stock_count ?? 0)}
            sub="needs restock"
            icon={FiXCircle}
          />
          <KPICard
            label="Deliveries Today"
            value={loading ? "…" : (kpis?.deliveries_today ?? 0)}
            sub="expected arrivals"
            icon={FiTruck}
          />
        </div>
      </section>

      {/* STOCK MOVEMENT FLOW */}
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <header className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
              <FiRepeat size={18} />
            </div>
            <div>
              <h2 className="text-[1.05rem] font-semibold tracking-tight">Stock Movement Flow</h2>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">Inbound suppliers, product traces and outbound destinations.</p>
            </div>
          </div>
          {flowData?.date_range && (
            <span className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] bg-[var(--input-background)] px-2.5 py-1 rounded-full border border-[var(--border)] whitespace-nowrap">
              {new Date(flowData.date_range.start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – {new Date(flowData.date_range.end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
        </header>
        {flowData && flowData.nodes.length > 0 ? (
          <LogisticsOverview data={flowData} />
        ) : (
          <div className="flex items-center justify-center h-40 text-[var(--muted-foreground)] animate-pulse">Loading logistics...</div>
        )}
      </section>

      {/* PRODUCTS TABLE */}
      <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between border-b border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
              <FiPackage size={18} />
            </div>
            <div>
              <h3 className="text-[1.05rem] font-semibold tracking-tight">Active Inventory</h3>
              <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Filter and inspect every SKU.</p>
            </div>
          </div>
          <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] bg-[var(--input-background)] px-2.5 py-1 rounded-full border border-[var(--border)] whitespace-nowrap">
            {totalProducts} SKUs
          </div>
        </div>

        <div className="px-5 py-4 flex flex-col sm:flex-row gap-3 border-b border-[var(--border)]">
          <div className="relative flex-1">
            <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" />
            <input
              type="text"
              placeholder="Search by product name or SKU..."
              className="w-full pl-9 pr-4 py-2 bg-[var(--input-background)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 transition-all"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <select
                className="appearance-none bg-[var(--input-background)] border border-[var(--border)] py-2 pl-3 pr-9 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 cursor-pointer"
                value={category}
                onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              >
                <option value="All">All Categories</option>
                <option value="SALES">Sales</option>
                <option value="INVENTORY">Inventory</option>
                <option value="GENERAL">General</option>
                <option value="Electronics">Electronics</option>
                <option value="Furniture">Furniture</option>
                <option value="Lighting">Lighting</option>
                <option value="Accessories">Accessories</option>
              </select>
              <FiFilter className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none" size={14} />
            </div>
            <div className="relative">
              <select
                className="appearance-none bg-[var(--input-background)] border border-[var(--border)] py-2 pl-3 pr-9 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 cursor-pointer"
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              >
                <option value="All">All Statuses</option>
                <option value="OK">Healthy (OK)</option>
                <option value="LOW">Low Stock</option>
                <option value="OUT">Out of Stock</option>
              </select>
              <FiFilter className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none" size={14} />
            </div>
          </div>
        </div>

        {loadingProducts ? (
          <p className="px-5 py-8 text-sm text-[var(--muted-foreground)]">Loading products…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--input-background)]">
                  {['Product', 'Category', 'Stock', 'Min Stock', 'Health'].map(h => (
                    <th key={h} className="text-left px-5 py-2.5 text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {products.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-[var(--muted-foreground)]">
                      No products found matching the criteria.
                    </td>
                  </tr>
                ) : (
                  products.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => setSelectedProduct(p)}
                      className="group border-t border-[var(--border)] hover:bg-[var(--input-background)] cursor-pointer transition-colors"
                    >
                      <td className="px-5 py-3">
                        <p className="font-semibold group-hover:text-[var(--primary)] transition-colors">{p.name}</p>
                        <p className="text-xs text-[var(--muted-foreground)] font-mono mt-0.5">{p.sku}</p>
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--input-background)] text-[var(--muted-foreground)] text-[11px] font-medium border border-[var(--border)]">
                          {p.category}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <span className="font-semibold">{p.stock_count}</span>
                      </td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)]">{p.min_stock}</td>
                      <td className="px-5 py-3">
                        <StatusBadge status={p.status} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {!loadingProducts && products.length > 0 && (
          <div className="px-5 py-3.5 border-t border-[var(--border)] bg-[var(--input-background)] flex items-center justify-between">
            <span className="text-sm text-[var(--muted-foreground)]">
              Showing {(page - 1) * 10 + 1} to {Math.min(page * 10, totalProducts || 0)} of {totalProducts || 0} items
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
                className="px-3 py-1.5 text-sm font-medium border border-[var(--border)] rounded-lg bg-[var(--card)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--input-background)] transition-colors"
              >
                Previous
              </button>
              <button
                disabled={page * 10 >= (totalProducts || 0)}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 text-sm font-medium border border-[var(--border)] rounded-lg bg-[var(--card)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--input-background)] transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>

      <DetailDrawer
        open={!!selectedProduct}
        onClose={() => setSelectedProduct(null)}
        product={selectedProduct}
      />
    </div>
  );
}
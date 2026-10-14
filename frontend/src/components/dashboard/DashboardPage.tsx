import { useAuth } from '../../context/AuthContext'
import CeoDashboard from '../ceo/CeoDashboard'
import HrDashboard from '../hr/HrDashboard'
import ItDashboard from '../it/ItDashboard'
import SalesDashboard from '../sales/SalesDashboard'
import InventoryDashboard from '../inventory/InventoryDashboard'

const DashboardPage = () => {
  const { user } = useAuth()

  if (!user) {
    return (
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <h2 className="text-lg font-semibold">Loading...</h2>
      </section>
    )
  }

  switch (user.role) {
    case 'CEO':
      return <CeoDashboard />
    case 'HR':
      return <HrDashboard />
    case 'IT':
      return <ItDashboard />
    case 'SALES':
      return <SalesDashboard />
    case 'INVENTORY':
      return <InventoryDashboard />
    default:
      return (
        <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
          <h2 className="text-lg font-semibold">Dashboard</h2>
          <p className="text-sm text-black/60 mt-1">No dashboard available for your role.</p>
        </section>
      )
  }
}

export default DashboardPage
import { Navigate } from 'react-router-dom';
import type { Role } from '../api/auth';
import { useAuth } from '../context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: Role;
  requiredRoles?: Role[];
}

export function ProtectedRoute({ children, requiredRole, requiredRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) return <div>Loading...</div>;

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const allowedRoles = requiredRoles ?? (requiredRole ? [requiredRole] : []);

  if (allowedRoles.length > 0 && user?.role !== 'CEO' && (!user?.role || !allowedRoles.includes(user.role))) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}
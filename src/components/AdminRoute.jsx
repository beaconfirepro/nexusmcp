import { Outlet } from 'react-router-dom';
import { useAuth } from '@/lib/AuthContext';
import NoAccess from '@/components/NoAccess';

export default function AdminRoute() {
  const { user } = useAuth();
  if (user?.role !== 'admin') {
    return <NoAccess />;
  }
  return <Outlet />;
}
import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography } from 'antd';
import {
  DashboardOutlined, SettingOutlined, AuditOutlined,
  TableOutlined, FundOutlined, TeamOutlined, DatabaseOutlined,
} from '@ant-design/icons';
import FilterPanel from '../filters/FilterPanel';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/setup', icon: <SettingOutlined />, label: 'Setup' },
  { key: '/projects', icon: <DatabaseOutlined />, label: 'Proyectos' },
  { key: '/dashboard', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/convenios', icon: <FundOutlined />, label: 'Convenios' },
  { key: '/calidad', icon: <TeamOutlined />, label: 'Calidad Contractual' },
  { key: '/audit', icon: <AuditOutlined />, label: 'Auditoría' },
  { key: '/records', icon: <TableOutlined />, label: 'Registros' },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [filterCollapsed, setFilterCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={200}
      >
        <div style={{ padding: '16px', textAlign: 'center' }}>
          <Typography.Text strong style={{ color: '#fff', fontSize: collapsed ? 14 : 18 }}>
            {collapsed ? 'MD' : 'MuniData'}
          </Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{
          background: '#fff', padding: '0 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: '1px solid #f0f0f0',
        }}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Dashboard BI Municipal - Transparencia Activa Chile
          </Typography.Title>
          <Typography.Text
            style={{ cursor: 'pointer', color: '#1677ff' }}
            onClick={() => setFilterCollapsed(!filterCollapsed)}
          >
            {filterCollapsed ? 'Mostrar Filtros' : 'Ocultar Filtros'}
          </Typography.Text>
        </Header>
        <Layout>
          {!filterCollapsed && (
            <Sider width={280} theme="light" style={{ borderRight: '1px solid #f0f0f0', overflow: 'auto' }}>
              <FilterPanel />
            </Sider>
          )}
          <Content style={{ padding: 16, background: '#f5f5f5', overflow: 'auto' }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}

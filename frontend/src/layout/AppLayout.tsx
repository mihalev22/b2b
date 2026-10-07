import { Layout, Menu } from 'antd';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { texts } from '../texts';

const { Header, Content } = Layout;

const menuItems = [
  { key: 'upload', label: <Link to="/">{texts.nav.upload}</Link> },
  { key: 'history', label: <Link to="/history">{texts.nav.history}</Link> },
];

function getSelectedKeys(pathname: string): string[] {
  if (pathname === '/') return ['upload'];
  if (pathname.startsWith('/history')) return ['history'];
  return [];
}

export default function AppLayout() {
  const { pathname } = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          paddingInline: 16,
          background: '#fff',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Link
          to="/"
          style={{ color: 'inherit', fontWeight: 600, fontSize: 16, whiteSpace: 'nowrap' }}
        >
          {texts.appName}
        </Link>
        <Menu
          mode="horizontal"
          items={menuItems}
          selectedKeys={getSelectedKeys(pathname)}
          style={{ flex: 1, minWidth: 0, borderBottom: 'none' }}
        />
      </Header>
      <Content style={{ padding: 16 }}>
        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          <Outlet />
        </div>
      </Content>
    </Layout>
  );
}

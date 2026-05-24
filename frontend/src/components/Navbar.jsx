import { Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { BookOutlined, MessageOutlined, FileTextOutlined, HomeOutlined } from '@ant-design/icons'

const Navbar = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const items = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: '首页',
    },
    {
      key: '/research',
      icon: <BookOutlined />,
      label: '智能研究',
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: '学术对话',
    },
    {
      key: '/documents',
      icon: <FileTextOutlined />,
      label: '文献管理',
    },
  ]

  return (
    <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      <div style={{ 
        color: 'white', 
        fontSize: '20px', 
        fontWeight: 'bold', 
        marginLeft: '24px',
        marginRight: '48px'
      }}>
        🧬 AI Scientist
      </div>
      <Menu
        theme="dark"
        mode="horizontal"
        selectedKeys={[location.pathname]}
        items={items}
        onClick={({ key }) => navigate(key)}
        style={{ flex: 1, minWidth: 0 }}
      />
    </div>
  )
}

export default Navbar

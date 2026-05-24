import { Card, Row, Col, Typography, Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import { BookOutlined, MessageOutlined, FileTextOutlined } from '@ant-design/icons'

const { Title, Paragraph } = Typography

const Home = () => {
  const navigate = useNavigate()

  const features = [
    {
      icon: <BookOutlined style={{ fontSize: '48px', color: '#1890ff' }} />,
      title: '智能研究',
      description: '基于千问大模型的自动文献综述和研究报告生成',
      action: () => navigate('/research'),
      btnText: '开始研究'
    },
    {
      icon: <MessageOutlined style={{ fontSize: '48px', color: '#52c41a' }} />,
      title: '学术对话',
      description: '与 AI 进行专业的学术讨论和问题解答',
      action: () => navigate('/chat'),
      btnText: '开始对话'
    },
    {
      icon: <FileTextOutlined style={{ fontSize: '48px', color: '#fa8c16' }} />,
      title: '文献管理',
      description: '上传、管理和智能检索您的学术文献库',
      action: () => navigate('/documents'),
      btnText: '管理文献'
    }
  ]

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '48px' }}>
        <Title level={1}>欢迎使用 AI Scientist</Title>
        <Paragraph style={{ fontSize: '18px', color: '#666' }}>
          基于千问大模型的智能科研助手，助力学术研究
        </Paragraph>
      </div>

      <Row gutter={[24, 24]}>
        {features.map((feature, index) => (
          <Col xs={24} md={8} key={index}>
            <Card
              hoverable
              style={{ height: '100%' }}
              bodyStyle={{ textAlign: 'center', padding: '32px' }}
            >
              <div style={{ marginBottom: '16px' }}>{feature.icon}</div>
              <Title level={3}>{feature.title}</Title>
              <Paragraph style={{ marginBottom: '24px' }}>
                {feature.description}
              </Paragraph>
              <Button type="primary" size="large" onClick={feature.action}>
                {feature.btnText}
              </Button>
            </Card>
          </Col>
        ))}
      </Row>

      <Card style={{ marginTop: '48px' }}>
        <Title level={2}>项目简介</Title>
        <Paragraph>
          本项目是为挑战杯 XH-202619 开发的基于 Qwen/千问大模型的 AI Scientist 系统。
          系统集成了智能文献检索、自动研究报告生成、学术对话等功能，
          旨在通过 AI 技术提升科研效率。
        </Paragraph>
        <Paragraph>
          <strong>技术栈：</strong>FastAPI + React + FAISS + MySQL
        </Paragraph>
      </Card>
    </div>
  )
}

export default Home

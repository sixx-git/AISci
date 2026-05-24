import { useState } from 'react'
import { Card, Form, Input, Select, Button, Spin, Typography, Alert } from 'antd'
import { ResearchOutlined } from '@ant-design/icons'
import api from '../services/api'

const { TextArea } = Input
const { Title, Paragraph } = Typography
const { Option } = Select

const Research = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async (values) => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await api.post('/research/generate', {
        topic: values.topic,
        keywords: values.keywords ? values.keywords.split(',').map(k => k.trim()) : [],
        research_type: values.research_type
      })
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || '生成失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Title level={2}>
        <ResearchOutlined style={{ marginRight: '8px' }} />
        智能研究报告生成
      </Title>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={12}>
          <Card title="研究配置">
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSubmit}
              initialValues={{
                research_type: 'literature_review'
              }}
            >
              <Form.Item
                name="topic"
                label="研究主题"
                rules={[{ required: true, message: '请输入研究主题' }]}
              >
                <Input placeholder="例如：深度学习在医学影像中的应用" size="large" />
              </Form.Item>

              <Form.Item
                name="keywords"
                label="关键词（可选，用逗号分隔）"
              >
                <Input placeholder="例如：深度学习, 医学影像, 计算机辅助诊断" />
              </Form.Item>

              <Form.Item
                name="research_type"
                label="研究类型"
                rules={[{ required: true, message: '请选择研究类型' }]}
              >
                <Select size="large">
                  <Option value="literature_review">文献综述</Option>
                  <Option value="research_proposal">研究 proposal</Option>
                  <Option value="experiment_design">实验设计</Option>
                  <Option value="data_analysis">数据分析方案</Option>
                </Select>
              </Form.Item>

              <Form.Item>
                <Button type="primary" size="large" htmlType="submit" loading={loading} block>
                  生成研究报告
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="生成结果">
            <Spin spinning={loading}>
              {error && (
                <Alert message="错误" description={error} type="error" showIcon style={{ marginBottom: '16px' }} />
              )}

              {result && (
                <div>
                  <Alert
                    message={`生成成功！耗时 ${result.execution_time.toFixed(2)} 秒`}
                    type="success"
                    showIcon
                    style={{ marginBottom: '16px' }}
                  />
                  <Title level={4}>{result.title}</Title>
                  <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{result.content}</Paragraph>
                </div>
              )}

              {!loading && !result && !error && (
                <div style={{ textAlign: 'center', color: '#999', padding: '48px' }}>
                  请配置研究参数后点击生成按钮
                </div>
              )}
            </Spin>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Research

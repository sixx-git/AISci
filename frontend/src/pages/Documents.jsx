import { useState, useEffect } from 'react'
import { Card, Table, Button, Upload, Alert, Tag, Space } from 'antd'
import { InboxOutlined, FileTextOutlined } from '@ant-design/icons'
import api from '../services/api'

const { Dragger } = Upload

const Documents = () => {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState(null)

  const loadDocuments = async () => {
    setLoading(true)
    try {
      const response = await api.get('/documents/list')
      setDocuments(response.data.documents)
    } catch (err) {
      console.error('加载文档失败:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [])

  const handleUpload = async (file) => {
    setUploading(true)
    setMessage(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setMessage({ type: 'success', text: `文件 ${response.data.filename} 上传成功！` })
      loadDocuments()
    } catch (err) {
      setMessage({ type: 'error', text: '上传失败，请稍后重试' })
    } finally {
      setUploading(false)
    }

    return false
  }

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (text) => (
        <span>
          <FileTextOutlined style={{ marginRight: '8px' }} />
          {text}
        </span>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const color = status === 'processed' ? 'green' : 'orange'
        return <Tag color={color}>{status === 'processed' ? '已处理' : '处理中'}</Tag>
      }
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => new Date(date).toLocaleString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="middle">
          <Button size="small">预览</Button>
          <Button size="small" danger>删除</Button>
        </Space>
      )
    }
  ]

  return (
    <div>
      <h2>文献管理</h2>

      {message && (
        <Alert
          message={message.text}
          type={message.type}
          showIcon
          closable
          style={{ marginBottom: '16px' }}
          onClose={() => setMessage(null)}
        />
      )}

      <Card title="上传文献" style={{ marginBottom: '24px' }}>
        <Dragger
          name="file"
          multiple={false}
          beforeUpload={handleUpload}
          showUploadList={false}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">支持 .txt, .pdf, .docx 等格式</p>
        </Dragger>
      </Card>

      <Card title="文献列表">
        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
        />
      </Card>
    </div>
  )
}

export default Documents

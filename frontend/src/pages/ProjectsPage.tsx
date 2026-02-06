import { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Select,
  Space, Typography, Popconfirm, message, Tag, Descriptions,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, DatabaseOutlined,
  FolderOpenOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import {
  fetchProjects, createProject, deleteProject, deleteProjectData,
} from '../services/api';
import { useFilterStore } from '../stores/filterStore';
import { useNavigate } from 'react-router-dom';
import type { Project, ProjectDeleteResult } from '../types';
import { MONTH_NAMES } from '../types';

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteResultModal, setDeleteResultModal] = useState<ProjectDeleteResult | null>(null);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { filters, setFilters } = useFilterStore();

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchProjects();
      setProjects(data);
    } catch {
      message.error('Error al cargar los proyectos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreate = async (values: {
    name: string;
    description?: string;
    municipality_code: string;
    area: string;
    year: number;
  }) => {
    try {
      await createProject({
        ...values,
        months: filters.months,
        contract_types: filters.contract_types,
        convenios: filters.convenios,
      });
      message.success('Proyecto guardado correctamente');
      setCreateModalOpen(false);
      form.resetFields();
      loadProjects();
    } catch {
      message.error('Error al guardar el proyecto');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteProject(id);
      message.success('Proyecto eliminado');
      loadProjects();
    } catch {
      message.error('Error al eliminar el proyecto');
    }
  };

  const handleDeleteData = async (project: Project) => {
    Modal.confirm({
      title: 'Eliminar datos del proyecto',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <p>
            Se eliminarán <strong>todos los registros</strong> de la base de datos
            asociados al municipio <strong>{project.municipality_code}</strong>,
            área <strong>{project.area}</strong>, año <strong>{project.year}</strong>.
          </p>
          <p>Esto incluye: honorarios, contrata, planta, escalas de remuneración,
            excepciones de auditoría y ejecuciones de scraping.</p>
          <p><strong>Esta acción no se puede deshacer.</strong></p>
        </div>
      ),
      okText: 'Eliminar datos',
      okType: 'danger',
      cancelText: 'Cancelar',
      onOk: async () => {
        try {
          const result = await deleteProjectData(project.id);
          setDeleteResultModal(result);
          loadProjects();
        } catch {
          message.error('Error al eliminar los datos');
        }
      },
    });
  };

  const handleLoadProject = (project: Project) => {
    setFilters({
      municipality_code: project.municipality_code,
      area: project.area,
      year: project.year,
      months: project.months || [1,2,3,4,5,6,7,8,9,10,11,12],
      contract_types: project.contract_types || ['HONORARIOS','CONTRATA','PLANTA'],
      convenios: project.convenios || [],
    });
    message.success(`Proyecto "${project.name}" cargado en filtros`);
    navigate('/dashboard');
  };

  const columns = [
    {
      title: 'Nombre',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Project) => (
        <div>
          <Typography.Text strong>{name}</Typography.Text>
          {record.description && (
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {record.description}
              </Typography.Text>
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Municipio',
      dataIndex: 'municipality_code',
      key: 'municipality_code',
      width: 100,
    },
    {
      title: 'Área',
      dataIndex: 'area',
      key: 'area',
      width: 80,
    },
    {
      title: 'Año',
      dataIndex: 'year',
      key: 'year',
      width: 70,
    },
    {
      title: 'Tipos',
      dataIndex: 'contract_types',
      key: 'contract_types',
      width: 200,
      render: (types: string[]) => (
        <Space size={2} wrap>
          {(types || []).map(ct => (
            <Tag key={ct} color={
              ct === 'HONORARIOS' ? 'blue' :
              ct === 'CONTRATA' ? 'green' : 'orange'
            }>{ct}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: 'Creado',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
      render: (v: string) => v ? new Date(v).toLocaleDateString('es-CL') : '-',
    },
    {
      title: 'Acciones',
      key: 'actions',
      width: 280,
      render: (_: unknown, record: Project) => (
        <Space size={4}>
          <Button
            size="small"
            type="primary"
            icon={<FolderOpenOutlined />}
            onClick={() => handleLoadProject(record)}
          >
            Cargar
          </Button>
          <Button
            size="small"
            danger
            icon={<DatabaseOutlined />}
            onClick={() => handleDeleteData(record)}
          >
            Borrar datos
          </Button>
          <Popconfirm
            title="Eliminar proyecto"
            description="Se eliminará solo el proyecto, no los datos."
            onConfirm={() => handleDelete(record.id)}
            okText="Eliminar"
            cancelText="Cancelar"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Eliminar
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={
          <Space>
            <DatabaseOutlined />
            <span>Proyectos Guardados</span>
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => {
            form.setFieldsValue({
              municipality_code: filters.municipality_code,
              area: filters.area,
              year: filters.year,
            });
            setCreateModalOpen(true);
          }}>
            Guardar como Proyecto
          </Button>
        }
      >
        <Typography.Paragraph type="secondary">
          Guarda configuraciones de bases de datos como proyectos para acceder rápidamente
          a ellos. También puedes eliminar todos los datos asociados a un proyecto si ya no los necesitas.
        </Typography.Paragraph>

        <Table
          dataSource={projects}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="small"
          locale={{ emptyText: 'No hay proyectos guardados. Crea uno con el botón de arriba.' }}
        />
      </Card>

      {/* Create Project Modal */}
      <Modal
        title="Guardar como Proyecto"
        open={createModalOpen}
        onCancel={() => { setCreateModalOpen(false); form.resetFields(); }}
        footer={null}
      >
        <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
          Se guardarán los filtros activos (meses, tipos de vínculo y convenios seleccionados)
          junto con la configuración base del proyecto.
        </Typography.Paragraph>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label="Nombre del Proyecto"
            rules={[{ required: true, message: 'Ingresa un nombre' }]}
          >
            <Input placeholder="Ej: Análisis Salud Municipal 2025" />
          </Form.Item>
          <Form.Item name="description" label="Descripción (opcional)">
            <Input.TextArea rows={2} placeholder="Breve descripción del proyecto..." />
          </Form.Item>
          <Form.Item
            name="municipality_code"
            label="Código Municipio"
            rules={[{ required: true, message: 'Ingresa el código' }]}
          >
            <Input placeholder="Ej: 280" />
          </Form.Item>
          <Form.Item name="area" label="Área" initialValue="Salud">
            <Select options={[
              { value: 'Salud', label: 'Salud' },
              { value: 'Educación', label: 'Educación' },
            ]} />
          </Form.Item>
          <Form.Item
            name="year"
            label="Año"
            rules={[{ required: true, message: 'Selecciona un año' }]}
          >
            <InputNumber min={2015} max={2030} style={{ width: '100%' }} />
          </Form.Item>

          <Descriptions size="small" column={1} bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Meses seleccionados">
              {filters.months.length === 12
                ? 'Todos'
                : filters.months.map(m => MONTH_NAMES[m]?.substring(0, 3)).join(', ')}
            </Descriptions.Item>
            <Descriptions.Item label="Tipos de vínculo">
              {filters.contract_types.join(', ')}
            </Descriptions.Item>
            <Descriptions.Item label="Convenios">
              {filters.convenios.length > 0 ? filters.convenios.join(', ') : 'Todos'}
            </Descriptions.Item>
          </Descriptions>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => { setCreateModalOpen(false); form.resetFields(); }}>
                Cancelar
              </Button>
              <Button type="primary" htmlType="submit" icon={<PlusOutlined />}>
                Guardar Proyecto
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Delete Data Result Modal */}
      <Modal
        title="Resultado de la eliminación"
        open={deleteResultModal !== null}
        onOk={() => setDeleteResultModal(null)}
        onCancel={() => setDeleteResultModal(null)}
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        {deleteResultModal && (
          <div>
            <Typography.Paragraph>{deleteResultModal.detail}</Typography.Paragraph>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="Honorarios">
                {deleteResultModal.deleted.honorarios} registros
              </Descriptions.Item>
              <Descriptions.Item label="Contrata">
                {deleteResultModal.deleted.contrata} registros
              </Descriptions.Item>
              <Descriptions.Item label="Planta">
                {deleteResultModal.deleted.planta} registros
              </Descriptions.Item>
              <Descriptions.Item label="Escalas de remuneración">
                {deleteResultModal.deleted.escalas} registros
              </Descriptions.Item>
              <Descriptions.Item label="Excepciones de auditoría">
                {deleteResultModal.deleted.audit_exceptions} registros
              </Descriptions.Item>
              <Descriptions.Item label="Ejecuciones de scraping">
                {deleteResultModal.deleted.scrape_runs} registros
              </Descriptions.Item>
            </Descriptions>
          </div>
        )}
      </Modal>
    </div>
  );
}

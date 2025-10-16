import type { Meta, StoryObj } from '@storybook/react-vite';
import React from 'react';
import { Button, Card, CardBody, Chip } from '@heroui/react';
import { useToast } from '@abase/ui';
import {
  CheckCircledIcon,
  CrossCircledIcon,
  ExclamationTriangleIcon,
  InfoCircledIcon,
  BellIcon,
  RocketIcon,
} from '@radix-ui/react-icons';

const meta: Meta = {
  title: 'Advanced/Notifications & Toasts',
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj;

export const ToastExamples: Story = {
  render: () => {
    const { addToast } = useToast();

    return (
      <div className="space-y-6 p-8">
        <div>
          <h2 className="text-2xl font-bold mb-4">Toast Notifications</h2>
          <p className="text-default-500 mb-6">
            Clique nos botões abaixo para ver diferentes tipos de toasts.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Button
            color="success"
            onPress={() =>
              addToast({
                type: 'success',
                title: 'Sucesso!',
                description: 'Sua ação foi concluída com sucesso.',
              })
            }
          >
            Success Toast
          </Button>

          <Button
            color="danger"
            onPress={() =>
              addToast({
                type: 'error',
                title: 'Erro!',
                description: 'Algo deu errado. Por favor, tente novamente.',
              })
            }
          >
            Error Toast
          </Button>

          <Button
            color="warning"
            onPress={() =>
              addToast({
                type: 'warning',
                title: 'Atenção!',
                description: 'Esta ação pode ter consequências.',
              })
            }
          >
            Warning Toast
          </Button>

          <Button
            color="primary"
            onPress={() =>
              addToast({
                type: 'info',
                title: 'Informação',
                description: 'Aqui está uma informação importante.',
              })
            }
          >
            Info Toast
          </Button>

          <Button
            variant="bordered"
            onPress={() =>
              addToast({
                type: 'success',
                title: 'Com Ação',
                description: 'Este toast tem uma ação personalizada.',
                action: {
                  label: 'Desfazer',
                  onClick: () => alert('Ação desfeita!'),
                },
              })
            }
          >
            With Action
          </Button>

          <Button
            variant="bordered"
            onPress={() =>
              addToast({
                type: 'info',
                title: 'Duração Personalizada',
                description: 'Este toast dura apenas 2 segundos.',
                duration: 2000,
              })
            }
          >
            Short Duration
          </Button>

          <Button
            variant="bordered"
            onPress={() =>
              addToast({
                type: 'warning',
                title: 'Sem Auto-Close',
                description: 'Este toast não fecha automaticamente.',
                duration: 0,
              })
            }
          >
            No Auto Close
          </Button>

          <Button
            variant="bordered"
            onPress={() => {
              addToast({
                type: 'success',
                title: 'Toast 1',
                description: 'Primeiro toast',
              });
              setTimeout(() => {
                addToast({
                  type: 'info',
                  title: 'Toast 2',
                  description: 'Segundo toast',
                });
              }, 500);
              setTimeout(() => {
                addToast({
                  type: 'warning',
                  title: 'Toast 3',
                  description: 'Terceiro toast',
                });
              }, 1000);
            }}
          >
            Multiple Toasts
          </Button>
        </div>
      </div>
    );
  },
};

export const InlineAlerts: Story = {
  render: () => (
    <div className="space-y-6 max-w-2xl p-8">
      <div>
        <h2 className="text-2xl font-bold mb-4">Inline Alerts</h2>
        <p className="text-default-500 mb-6">
          Alerts inline são úteis para feedback contextual.
        </p>
      </div>

      <div className="space-y-4">
        {/* Success Alert */}
        <Card className="border-l-4 border-l-success bg-success-50">
          <CardBody className="flex-row items-start gap-3 p-4">
            <CheckCircledIcon className="w-5 h-5 text-success-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-semibold text-success-900 mb-1">
                Operação bem-sucedida
              </h4>
              <p className="text-sm text-success-700">
                Suas alterações foram salvas com sucesso. Você pode continuar trabalhando.
              </p>
            </div>
          </CardBody>
        </Card>

        {/* Error Alert */}
        <Card className="border-l-4 border-l-danger bg-danger-50">
          <CardBody className="flex-row items-start gap-3 p-4">
            <CrossCircledIcon className="w-5 h-5 text-danger-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-semibold text-danger-900 mb-1">
                Erro na operação
              </h4>
              <p className="text-sm text-danger-700">
                Não foi possível processar sua solicitação. Verifique os dados e tente novamente.
              </p>
              <Button
                size="sm"
                color="danger"
                variant="flat"
                className="mt-2"
              >
                Tentar Novamente
              </Button>
            </div>
          </CardBody>
        </Card>

        {/* Warning Alert */}
        <Card className="border-l-4 border-l-warning bg-warning-50">
          <CardBody className="flex-row items-start gap-3 p-4">
            <ExclamationTriangleIcon className="w-5 h-5 text-warning-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-semibold text-warning-900 mb-1">
                Atenção necessária
              </h4>
              <p className="text-sm text-warning-700">
                Existem algumas pendências que precisam ser resolvidas antes de continuar.
              </p>
              <div className="flex gap-2 mt-2">
                <Button size="sm" color="warning" variant="flat">
                  Ver Pendências
                </Button>
                <Button size="sm" variant="light">
                  Ignorar
                </Button>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Info Alert */}
        <Card className="border-l-4 border-l-primary bg-primary-50">
          <CardBody className="flex-row items-start gap-3 p-4">
            <InfoCircledIcon className="w-5 h-5 text-primary-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-semibold text-primary-900 mb-1">
                Informação importante
              </h4>
              <p className="text-sm text-primary-700">
                Uma nova versão do sistema está disponível. Atualize para aproveitar as novidades.
              </p>
              <Button
                size="sm"
                color="primary"
                variant="flat"
                className="mt-2"
              >
                Atualizar Agora
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  ),
};

export const NotificationBadges: Story = {
  render: () => (
    <div className="space-y-6 max-w-2xl p-8">
      <div>
        <h2 className="text-2xl font-bold mb-4">Notification Badges</h2>
        <p className="text-default-500 mb-6">
          Badges para indicar notificações e estados.
        </p>
      </div>

      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold mb-3">Notification Cards</h3>
          <div className="space-y-3">
            <Card className="hover:bg-default-50 cursor-pointer transition-colors">
              <CardBody className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-success-100 flex items-center justify-center flex-shrink-0">
                    <CheckCircledIcon className="w-5 h-5 text-success-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-semibold text-sm">
                        Cadastro aprovado
                      </p>
                      <span className="text-xs text-default-400">2 min</span>
                    </div>
                    <p className="text-sm text-default-600">
                      O cadastro #1234 foi aprovado com sucesso.
                    </p>
                  </div>
                  <div className="w-2 h-2 rounded-full bg-primary flex-shrink-0 mt-2" />
                </div>
              </CardBody>
            </Card>

            <Card className="hover:bg-default-50 cursor-pointer transition-colors">
              <CardBody className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-warning-100 flex items-center justify-center flex-shrink-0">
                    <ExclamationTriangleIcon className="w-5 h-5 text-warning-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-semibold text-sm">
                        Pendência identificada
                      </p>
                      <span className="text-xs text-default-400">15 min</span>
                    </div>
                    <p className="text-sm text-default-600">
                      Existem documentos pendentes no cadastro #1235.
                    </p>
                  </div>
                </div>
              </CardBody>
            </Card>

            <Card className="hover:bg-default-50 cursor-pointer transition-colors opacity-60">
              <CardBody className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
                    <RocketIcon className="w-5 h-5 text-primary-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-semibold text-sm">
                        Nova funcionalidade
                      </p>
                      <span className="text-xs text-default-400">1 hora</span>
                    </div>
                    <p className="text-sm text-default-600">
                      Agora você pode exportar relatórios em PDF.
                    </p>
                  </div>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-3">Status Badges</h3>
          <div className="flex flex-wrap gap-2">
            <Chip color="success" variant="flat" startContent={<CheckCircledIcon />}>
              Aprovado
            </Chip>
            <Chip color="danger" variant="flat" startContent={<CrossCircledIcon />}>
              Rejeitado
            </Chip>
            <Chip color="warning" variant="flat" startContent={<ExclamationTriangleIcon />}>
              Pendente
            </Chip>
            <Chip color="primary" variant="flat" startContent={<InfoCircledIcon />}>
              Em Análise
            </Chip>
            <Chip color="default" variant="flat" startContent={<BellIcon />}>
              Notificado
            </Chip>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-3">Badge Counters</h3>
          <div className="flex gap-4">
            <div className="relative inline-block">
              <Button color="primary" isIconOnly>
                <BellIcon className="w-5 h-5" />
              </Button>
              <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-danger text-xs text-white">
                5
              </span>
            </div>
            <div className="relative inline-block">
              <Button color="primary" variant="flat">
                Mensagens
              </Button>
              <span className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-danger text-xs text-white font-semibold">
                12
              </span>
            </div>
            <div className="relative inline-block">
              <Button color="default" variant="bordered">
                Pendências
                <Chip size="sm" color="warning" className="ml-2">3</Chip>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  ),
};

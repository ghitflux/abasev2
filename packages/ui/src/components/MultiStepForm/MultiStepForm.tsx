"use client";

import React from 'react';
import { Button, Card, CardBody, CardHeader, Divider } from '@heroui/react';
import { cn } from '../../utils/cn';

export interface Step {
  id: string;
  title: string;
  description?: string;
  isCompleted?: boolean;
  isActive?: boolean;
  isDisabled?: boolean;
}

export interface MultiStepFormProps {
  steps: Step[];
  currentStep: number;
  onStepChange: (stepIndex: number) => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onFinish?: () => void;
  children: React.ReactNode;
  className?: string;
  showNavigation?: boolean;
  showProgress?: boolean;
  allowStepNavigation?: boolean;
  nextButtonText?: string;
  previousButtonText?: string;
  finishButtonText?: string;
  isLoading?: boolean;
}

export function MultiStepForm({
  steps,
  currentStep,
  onStepChange,
  onNext,
  onPrevious,
  onFinish,
  children,
  className,
  showNavigation = true,
  showProgress = true,
  allowStepNavigation = true,
  nextButtonText = "Próximo",
  previousButtonText = "Anterior",
  finishButtonText = "Finalizar",
  isLoading = false,
}: MultiStepFormProps) {
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const currentStepData = steps[currentStep];

  const handleStepClick = (stepIndex: number) => {
    if (allowStepNavigation && stepIndex !== currentStep) {
      onStepChange(stepIndex);
    }
  };

  const handleNext = () => {
    if (onNext) {
      onNext();
    } else if (currentStep < steps.length - 1) {
      onStepChange(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (onPrevious) {
      onPrevious();
    } else if (currentStep > 0) {
      onStepChange(currentStep - 1);
    }
  };

  const handleFinish = () => {
    if (onFinish) {
      onFinish();
    }
  };

  return (
    <div className={cn("w-full max-w-4xl mx-auto", className)}>
      {/* Progress Steps */}
      {showProgress && (
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                {/* Step Circle */}
                <div
                  className={cn(
                    "flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors cursor-pointer",
                    step.isCompleted
                      ? "bg-success border-success text-white"
                      : step.isActive
                      ? "bg-primary border-primary text-white"
                      : step.isDisabled
                      ? "bg-default-100 border-default-300 text-default-400 cursor-not-allowed"
                      : "bg-default-50 border-default-300 text-default-600 hover:border-primary hover:text-primary"
                  )}
                  onClick={() => handleStepClick(index)}
                >
                  {step.isCompleted ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    <span className="text-sm font-medium">{index + 1}</span>
                  )}
                </div>

                {/* Step Info */}
                <div className="ml-3 min-w-0 flex-1">
                  <p
                    className={cn(
                      "text-sm font-medium",
                      step.isActive
                        ? "text-primary"
                        : step.isCompleted
                        ? "text-success"
                        : step.isDisabled
                        ? "text-default-400"
                        : "text-default-600"
                    )}
                  >
                    {step.title}
                  </p>
                  {step.description && (
                    <p
                      className={cn(
                        "text-xs",
                        step.isActive
                          ? "text-primary-600"
                          : step.isCompleted
                          ? "text-success-600"
                          : step.isDisabled
                          ? "text-default-400"
                          : "text-default-500"
                      )}
                    >
                      {step.description}
                    </p>
                  )}
                </div>

                {/* Connector Line */}
                {index < steps.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 h-0.5 mx-4 transition-colors",
                      step.isCompleted
                        ? "bg-success"
                        : "bg-default-200"
                    )}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current Step Header */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between w-full">
            <div>
              <h2 className="text-xl font-semibold text-default-700">
                {currentStepData.title}
              </h2>
              {currentStepData.description && (
                <p className="text-sm text-default-500 mt-1">
                  {currentStepData.description}
                </p>
              )}
            </div>
            <div className="text-sm text-default-400">
              Passo {currentStep + 1} de {steps.length}
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Form Content */}
      <Card>
        <CardBody className="p-6">
          {children}
        </CardBody>
      </Card>

      {/* Navigation */}
      {showNavigation && (
        <>
          <Divider className="my-6" />
          <div className="flex items-center justify-between">
            <Button
              variant="bordered"
              onPress={handlePrevious}
              disabled={isFirstStep || isLoading}
              className="min-w-24"
            >
              {previousButtonText}
            </Button>

            <div className="flex items-center space-x-2">
              {steps.map((_, index) => (
                <div
                  key={index}
                  className={cn(
                    "w-2 h-2 rounded-full transition-colors",
                    index === currentStep
                      ? "bg-primary"
                      : index < currentStep
                      ? "bg-success"
                      : "bg-default-200"
                  )}
                />
              ))}
            </div>

            {isLastStep ? (
              <Button
                color="primary"
                onPress={handleFinish}
                isLoading={isLoading}
                className="min-w-24"
              >
                {finishButtonText}
              </Button>
            ) : (
              <Button
                color="primary"
                onPress={handleNext}
                isLoading={isLoading}
                className="min-w-24"
              >
                {nextButtonText}
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

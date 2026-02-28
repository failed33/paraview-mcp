#include "ParaViewMCPDockWindow.h"

#include "bridge/ParaViewMCPBridgeController.h"

#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QVBoxLayout>
#include <QWidget>

ParaViewMCPDockWindow::ParaViewMCPDockWindow(QWidget* parent)
    : QDockWidget(QStringLiteral("ParaView MCP"), parent)
{
  this->setObjectName(QStringLiteral("ParaViewMCPDockWindow"));

  auto* container = new QWidget(this);
  auto* layout = new QVBoxLayout(container);
  auto* formLayout = new QFormLayout();

  this->HostField = new QLineEdit(container);
  this->PortField = new QSpinBox(container);
  this->PortField->setRange(1, 65535);
  this->TokenField = new QLineEdit(container);
  this->TokenField->setEchoMode(QLineEdit::Password);
  this->StatusLabel = new QLabel(container);
  this->LogOutput = new QPlainTextEdit(container);
  this->LogOutput->setReadOnly(true);
  this->LogOutput->setMaximumBlockCount(200);
  this->LogOutput->setMinimumHeight(140);

  formLayout->addRow(QStringLiteral("Listen Host"), this->HostField);
  formLayout->addRow(QStringLiteral("Listen Port"), this->PortField);
  formLayout->addRow(QStringLiteral("Auth Token"), this->TokenField);
  formLayout->addRow(QStringLiteral("Status"), this->StatusLabel);
  layout->addLayout(formLayout);

  auto* buttonLayout = new QHBoxLayout();
  this->StartButton = new QPushButton(QStringLiteral("Start Server"), container);
  this->StopButton = new QPushButton(QStringLiteral("Stop Server"), container);
  buttonLayout->addWidget(this->StartButton);
  buttonLayout->addWidget(this->StopButton);
  layout->addLayout(buttonLayout);
  layout->addWidget(this->LogOutput);

  this->setWidget(container);

  ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  controller.registerDockWindow(this);

  QObject::connect(this->StartButton,
                   &QPushButton::clicked,
                   this,
                   [this]()
                   {
                     ParaViewMCPBridgeController::instance().startServer(
                       this->HostField->text(),
                       static_cast<quint16>(this->PortField->value()),
                       this->TokenField->text());
                     this->syncState();
                   });

  QObject::connect(this->StopButton,
                   &QPushButton::clicked,
                   this,
                   [this]()
                   {
                     ParaViewMCPBridgeController::instance().stopServer();
                     this->syncState();
                   });

  QObject::connect(&controller,
                   &ParaViewMCPBridgeController::statusChanged,
                   this,
                   [this](const QString& status)
                   {
                     this->StatusLabel->setText(status);
                     this->syncState();
                   });

  QObject::connect(&controller,
                   &ParaViewMCPBridgeController::logChanged,
                   this,
                   [this](const QString& message) { this->LogOutput->setPlainText(message); });

  this->refreshFromController();
}

void ParaViewMCPDockWindow::refreshFromController()
{
  const ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  this->HostField->setText(controller.host());
  this->PortField->setValue(static_cast<int>(controller.port()));
  this->StatusLabel->setText(controller.lastStatus());
  this->LogOutput->setPlainText(controller.lastLog());
  this->syncState();
}

void ParaViewMCPDockWindow::syncState()
{
  const ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  const bool listening = controller.isListening();

  this->HostField->setEnabled(!listening);
  this->PortField->setEnabled(!listening);
  this->TokenField->setEnabled(!listening);
  this->StartButton->setEnabled(!listening);
  this->StopButton->setEnabled(listening);
}

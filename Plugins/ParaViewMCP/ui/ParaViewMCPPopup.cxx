#include "ParaViewMCPPopup.h"

#include "ParaViewMCPStateAppearance.h"
#include "bridge/ParaViewMCPBridgeController.h"

#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QScreen>
#include <QSpinBox>
#include <QToolButton>
#include <QVBoxLayout>

namespace
{
  constexpr int PopupWidth = 320;
} // namespace

ParaViewMCPPopup::ParaViewMCPPopup(QWidget* parent)
    : QFrame(parent, Qt::Popup | Qt::FramelessWindowHint)
{
  this->setFixedWidth(PopupWidth);
  this->setFrameShape(QFrame::StyledPanel);
  this->setFrameShadow(QFrame::Raised);

  auto* layout = new QVBoxLayout(this);
  layout->setContentsMargins(12, 12, 12, 12);
  layout->setSpacing(8);

  // --- Status row ---
  auto* statusRow = new QHBoxLayout();
  this->StatusDot = new QLabel(this);
  this->StatusDot->setFixedSize(10, 10);
  this->StatusText = new QLabel(QStringLiteral("Stopped"), this);
  auto font = this->StatusText->font();
  font.setBold(true);
  this->StatusText->setFont(font);
  statusRow->addWidget(this->StatusDot);
  statusRow->addWidget(this->StatusText);
  statusRow->addStretch();
  layout->addLayout(statusRow);

  // --- Form fields ---
  auto* formLayout = new QFormLayout();
  formLayout->setFieldGrowthPolicy(QFormLayout::ExpandingFieldsGrow);

  this->HostField = new QLineEdit(this);
  this->PortField = new QSpinBox(this);
  this->PortField->setRange(1, 65535);
  this->TokenField = new QLineEdit(this);
  this->TokenField->setEchoMode(QLineEdit::Password);

  formLayout->addRow(QStringLiteral("Host"), this->HostField);
  formLayout->addRow(QStringLiteral("Port"), this->PortField);
  formLayout->addRow(QStringLiteral("Token"), this->TokenField);
  layout->addLayout(formLayout);

  // --- Buttons ---
  auto* buttonLayout = new QHBoxLayout();
  this->StartButton = new QPushButton(QStringLiteral("Start Server"), this);
  this->StopButton = new QPushButton(QStringLiteral("Stop Server"), this);
  buttonLayout->addWidget(this->StartButton);
  buttonLayout->addWidget(this->StopButton);
  layout->addLayout(buttonLayout);

  // --- Collapsible log ---
  this->LogToggle = new QToolButton(this);
  this->LogToggle->setArrowType(Qt::RightArrow);
  this->LogToggle->setText(QStringLiteral(" Log"));
  this->LogToggle->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
  this->LogToggle->setAutoRaise(true);
  this->LogToggle->setCheckable(true);
  layout->addWidget(this->LogToggle);

  this->LogOutput = new QPlainTextEdit(this);
  this->LogOutput->setReadOnly(true);
  this->LogOutput->setMaximumBlockCount(200);
  this->LogOutput->setFixedHeight(140);
  this->LogOutput->setVisible(false);
  layout->addWidget(this->LogOutput);

  // --- Connections ---
  ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  controller.registerPopup(this);

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
                   [this](const QString& /*status*/) { this->syncState(); });

  QObject::connect(&controller,
                   &ParaViewMCPBridgeController::serverStateChanged,
                   this,
                   [this](ParaViewMCPBridgeController::ServerState state)
                   {
                     const auto appearance = appearanceForState(state);
                     this->StatusDot->setStyleSheet(
                       QStringLiteral("background-color: %1; border-radius: 5px;")
                         .arg(QLatin1String(appearance.Color)));
                     this->StatusText->setText(QLatin1String(appearance.Label));
                     this->StatusText->setStyleSheet(
                       QStringLiteral("color: %1;").arg(QLatin1String(appearance.Color)));
                   });

  QObject::connect(&controller,
                   &ParaViewMCPBridgeController::logChanged,
                   this,
                   [this](const QString& message) { this->LogOutput->setPlainText(message); });

  QObject::connect(this->LogToggle,
                   &QToolButton::toggled,
                   this,
                   [this](bool checked)
                   {
                     this->LogToggle->setArrowType(checked ? Qt::DownArrow : Qt::RightArrow);
                     this->LogOutput->setVisible(checked);
                     this->adjustSize();
                   });

  this->refreshFromController();
}

void ParaViewMCPPopup::showRelativeTo(QWidget* anchor)
{
  this->refreshFromController();

  if (anchor != nullptr)
  {
    QPoint pos = anchor->mapToGlobal(QPoint(0, anchor->height()));
    QScreen* screen = anchor->screen();
    if (screen != nullptr)
    {
      const QRect available = screen->availableGeometry();
      if (pos.x() + this->width() > available.right())
      {
        pos.setX(available.right() - this->width());
      }
      if (pos.y() + this->sizeHint().height() > available.bottom())
      {
        pos.setY(anchor->mapToGlobal(QPoint(0, 0)).y() - this->sizeHint().height());
      }
    }
    this->move(pos);
  }

  this->show();
}

void ParaViewMCPPopup::refreshFromController()
{
  const ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  this->HostField->setText(controller.host());
  this->PortField->setValue(static_cast<int>(controller.port()));
  this->TokenField->setText(controller.authToken());
  this->LogOutput->setPlainText(controller.lastLog());

  const auto appearance = appearanceForState(controller.serverState());
  this->StatusDot->setStyleSheet(QStringLiteral("background-color: %1; border-radius: 5px;")
                                   .arg(QLatin1String(appearance.Color)));
  this->StatusText->setText(QLatin1String(appearance.Label));
  this->StatusText->setStyleSheet(
    QStringLiteral("color: %1;").arg(QLatin1String(appearance.Color)));

  this->syncState();
}

void ParaViewMCPPopup::syncState()
{
  const ParaViewMCPBridgeController& controller = ParaViewMCPBridgeController::instance();
  const bool listening = controller.isListening();

  this->HostField->setEnabled(!listening);
  this->PortField->setEnabled(!listening);
  this->TokenField->setEnabled(!listening);
  this->StartButton->setEnabled(!listening);
  this->StopButton->setEnabled(listening);
}

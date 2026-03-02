#include "ParaViewMCPPopup.h"

#include "ParaViewMCPHistoryEntry.h"
#include "ParaViewMCPStateAppearance.h"
#include "bridge/ParaViewMCPBridgeController.h"

#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPushButton>
#include <QScreen>
#include <QScrollArea>
#include <QScrollBar>
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

  // --- Collapsible history ---
  auto* historyHeaderRow = new QHBoxLayout();
  this->HistoryToggle = new QToolButton(this);
  this->HistoryToggle->setArrowType(Qt::RightArrow);
  this->HistoryToggle->setText(QStringLiteral(" History"));
  this->HistoryToggle->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
  this->HistoryToggle->setAutoRaise(true);
  this->HistoryToggle->setCheckable(true);
  historyHeaderRow->addWidget(this->HistoryToggle);

  this->HistoryCountLabel = new QLabel(QStringLiteral("(0)"), this);
  historyHeaderRow->addWidget(this->HistoryCountLabel);
  historyHeaderRow->addStretch();
  layout->addLayout(historyHeaderRow);

  this->HistoryContainer = new QWidget();
  this->HistoryLayout = new QVBoxLayout(this->HistoryContainer);
  this->HistoryLayout->setContentsMargins(0, 0, 0, 0);
  this->HistoryLayout->setSpacing(2);
  this->HistoryLayout->addStretch();

  this->HistoryScroll = new QScrollArea(this);
  this->HistoryScroll->setWidgetResizable(true);
  this->HistoryScroll->setWidget(this->HistoryContainer);
  this->HistoryScroll->setFixedHeight(250);
  this->HistoryScroll->setVisible(false);
  layout->addWidget(this->HistoryScroll);

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
                     this->applyAppearance(appearance.Label, appearance.Color);
                   });

  QObject::connect(&controller,
                   &ParaViewMCPBridgeController::historyChanged,
                   this,
                   &ParaViewMCPPopup::onHistoryChanged);

  QObject::connect(this->HistoryToggle,
                   &QToolButton::toggled,
                   this,
                   [this](bool checked)
                   {
                     this->HistoryToggle->setArrowType(checked ? Qt::DownArrow : Qt::RightArrow);
                     this->HistoryScroll->setVisible(checked);
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
  this->rebuildHistoryEntries(controller.lastHistory());

  const auto appearance = appearanceForState(controller.serverState());
  this->applyAppearance(appearance.Label, appearance.Color);

  this->syncState();
}

void ParaViewMCPPopup::applyAppearance(const char* label, const char* color)
{
  this->StatusDot->setStyleSheet(
    QStringLiteral("background-color: %1; border-radius: 5px;").arg(QLatin1String(color)));
  this->StatusText->setText(QLatin1String(label));
  this->StatusText->setStyleSheet(QStringLiteral("color: %1;").arg(QLatin1String(color)));
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

void ParaViewMCPPopup::onHistoryChanged(const QString& historyJson)
{
  this->rebuildHistoryEntries(historyJson);
}

void ParaViewMCPPopup::onRestoreRequested(int entryId)
{
  const auto answer = QMessageBox::question(this,
                                            QStringLiteral("Restore Snapshot"),
                                            QStringLiteral("Restore pipeline to before step #%1?\n"
                                                           "This will remove all later history.")
                                              .arg(entryId),
                                            QMessageBox::Yes | QMessageBox::No,
                                            QMessageBox::No);
  if (answer == QMessageBox::Yes)
  {
    ParaViewMCPBridgeController::instance().restoreSnapshot(entryId);
  }
}

void ParaViewMCPPopup::rebuildHistoryEntries(const QString& historyJson)
{
  // Remove existing entry widgets (keep the trailing stretch)
  while (this->HistoryLayout->count() > 1)
  {
    QLayoutItem* item = this->HistoryLayout->takeAt(0);
    if (item->widget() != nullptr)
    {
      delete item->widget();
    }
    delete item;
  }

  const QJsonDocument doc = QJsonDocument::fromJson(historyJson.toUtf8());
  const QJsonArray entries = doc.array();

  this->HistoryCountLabel->setText(QStringLiteral("(%1)").arg(entries.size()));

  for (const auto& val : entries)
  {
    auto* entry = new ParaViewMCPHistoryEntry(val.toObject(), this->HistoryContainer);
    QObject::connect(entry,
                     &ParaViewMCPHistoryEntry::restoreRequested,
                     this,
                     &ParaViewMCPPopup::onRestoreRequested);
    this->HistoryLayout->insertWidget(this->HistoryLayout->count() - 1, entry);
  }

  // Auto-scroll to bottom
  QMetaObject::invokeMethod(
    this,
    [this]()
    {
      QScrollBar* bar = this->HistoryScroll->verticalScrollBar();
      bar->setValue(bar->maximum());
    },
    Qt::QueuedConnection);
}

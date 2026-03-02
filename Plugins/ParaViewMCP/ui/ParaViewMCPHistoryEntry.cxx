#include "ParaViewMCPHistoryEntry.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QToolButton>
#include <QVBoxLayout>

ParaViewMCPHistoryEntry::ParaViewMCPHistoryEntry(const QJsonObject& entry, QWidget* parent)
    : QFrame(parent)
{
  this->EntryId = entry.value(QStringLiteral("id")).toInt();
  this->HasSnapshot = entry.value(QStringLiteral("has_snapshot")).toBool();

  const QString command = entry.value(QStringLiteral("command")).toString();
  const QString timestamp = entry.value(QStringLiteral("timestamp")).toString();
  const QString status = entry.value(QStringLiteral("status")).toString();
  const bool isError = (status == QStringLiteral("error"));

  const QString code = entry.value(QStringLiteral("code")).isNull()
                         ? QString()
                         : entry.value(QStringLiteral("code")).toString();

  QString stdoutText;
  QString errorText;
  if (!entry.value(QStringLiteral("result")).isNull())
  {
    const QJsonObject result = entry.value(QStringLiteral("result")).toObject();
    stdoutText = result.value(QStringLiteral("stdout")).toString();
    errorText = result.value(QStringLiteral("error")).toString();
  }

  if (isError)
  {
    this->setStyleSheet(QStringLiteral("QFrame { background-color: rgba(255, 0, 0, 30); }"));
  }

  auto* mainLayout = new QVBoxLayout(this);
  mainLayout->setContentsMargins(4, 2, 4, 2);
  mainLayout->setSpacing(2);

  // --- Header row ---
  auto* headerRow = new QHBoxLayout();
  headerRow->setSpacing(4);

  this->ExpandToggle = new QToolButton(this);
  this->ExpandToggle->setArrowType(Qt::RightArrow);
  this->ExpandToggle->setAutoRaise(true);
  this->ExpandToggle->setCheckable(true);
  this->ExpandToggle->setFixedSize(16, 16);
  headerRow->addWidget(this->ExpandToggle);

  const QString statusText = isError ? QStringLiteral("ERR") : QStringLiteral("OK");
  const QString headerText =
    QStringLiteral("#%1 %2  %3  [%4]").arg(this->EntryId).arg(command, timestamp, statusText);
  this->HeaderLabel = new QLabel(headerText, this);
  this->HeaderLabel->setTextFormat(Qt::PlainText);
  headerRow->addWidget(this->HeaderLabel, 1);

  if (this->HasSnapshot)
  {
    this->RestoreButton = new QPushButton(QStringLiteral("Restore"), this);
    this->RestoreButton->setFixedHeight(20);
    QObject::connect(this->RestoreButton,
                     &QPushButton::clicked,
                     this,
                     [this]() { emit this->restoreRequested(this->EntryId); });
    headerRow->addWidget(this->RestoreButton);
  }

  mainLayout->addLayout(headerRow);

  // --- Collapsible details ---
  this->DetailsWidget = new QWidget(this);
  auto* detailsLayout = new QVBoxLayout(this->DetailsWidget);
  detailsLayout->setContentsMargins(20, 0, 0, 0);
  detailsLayout->setSpacing(2);

  QFont detailFont = this->font();
  detailFont.setPointSize(detailFont.pointSize() - 2);

  if (!code.isEmpty())
  {
    this->CodeLabel = new QLabel(this->DetailsWidget);
    this->CodeLabel->setFont(detailFont);
    this->CodeLabel->setTextFormat(Qt::PlainText);
    this->CodeLabel->setWordWrap(true);
    this->CodeLabel->setText(code);
    detailsLayout->addWidget(this->CodeLabel);
  }

  QString outputText;
  if (!stdoutText.isEmpty())
  {
    outputText = stdoutText;
  }
  if (!errorText.isEmpty())
  {
    if (!outputText.isEmpty())
    {
      outputText += QStringLiteral("\n");
    }
    outputText += errorText;
  }

  if (!outputText.isEmpty())
  {
    this->OutputLabel = new QLabel(this->DetailsWidget);
    this->OutputLabel->setFont(detailFont);
    this->OutputLabel->setTextFormat(Qt::PlainText);
    this->OutputLabel->setWordWrap(true);
    this->OutputLabel->setText(outputText);
    detailsLayout->addWidget(this->OutputLabel);
  }

  this->DetailsWidget->setVisible(false);
  mainLayout->addWidget(this->DetailsWidget);

  QObject::connect(
    this->ExpandToggle, &QToolButton::toggled, this, &ParaViewMCPHistoryEntry::toggleDetails);
}

int ParaViewMCPHistoryEntry::entryId() const
{
  return this->EntryId;
}

bool ParaViewMCPHistoryEntry::hasSnapshot() const
{
  return this->HasSnapshot;
}

void ParaViewMCPHistoryEntry::toggleDetails(bool expanded)
{
  this->ExpandToggle->setArrowType(expanded ? Qt::DownArrow : Qt::RightArrow);
  this->DetailsWidget->setVisible(expanded);
}

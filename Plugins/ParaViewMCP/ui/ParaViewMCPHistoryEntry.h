#pragma once

#include <QFrame>
#include <QJsonObject>

class QLabel;
class QPushButton;
class QToolButton;

class ParaViewMCPHistoryEntry : public QFrame
{
  Q_OBJECT

public:
  explicit ParaViewMCPHistoryEntry(const QJsonObject& entry, QWidget* parent = nullptr);

  [[nodiscard]] int entryId() const;
  [[nodiscard]] bool hasSnapshot() const;

signals:
  void restoreRequested(int entryId);

private:
  void toggleDetails(bool expanded);

  int EntryId = 0;
  bool HasSnapshot = false;
  QLabel* HeaderLabel = nullptr;
  QToolButton* ExpandToggle = nullptr;
  QWidget* DetailsWidget = nullptr;
  QLabel* CodeLabel = nullptr;
  QLabel* OutputLabel = nullptr;
  QPushButton* RestoreButton = nullptr;
};

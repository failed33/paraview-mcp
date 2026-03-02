#pragma once

#include <QFrame>

class QLabel;
class QLineEdit;
class QPushButton;
class QScrollArea;
class QSpinBox;
class QToolButton;
class QVBoxLayout;

class ParaViewMCPPopup : public QFrame
{
  Q_OBJECT

public:
  explicit ParaViewMCPPopup(QWidget* parent = nullptr);

  void showRelativeTo(QWidget* anchor);
  void refreshFromController();

private:
  void syncState();
  void onHistoryChanged(const QString& historyJson);
  void onRestoreRequested(int entryId);
  void rebuildHistoryEntries(const QString& historyJson);

  QLabel* StatusDot = nullptr;
  QLabel* StatusText = nullptr;
  QLineEdit* HostField = nullptr;
  QSpinBox* PortField = nullptr;
  QLineEdit* TokenField = nullptr;
  QPushButton* StartButton = nullptr;
  QPushButton* StopButton = nullptr;
  QToolButton* HistoryToggle = nullptr;
  QLabel* HistoryCountLabel = nullptr;
  QScrollArea* HistoryScroll = nullptr;
  QWidget* HistoryContainer = nullptr;
  QVBoxLayout* HistoryLayout = nullptr;
};

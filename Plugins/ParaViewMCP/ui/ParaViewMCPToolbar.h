#pragma once

#include <QToolBar>

class ParaViewMCPPopup;
class QLabel;
class QToolButton;
class QWidget;

class ParaViewMCPToolbar : public QToolBar
{
  Q_OBJECT

public:
  ParaViewMCPToolbar(const QString& title, QWidget* parent = nullptr);
  ParaViewMCPToolbar(QWidget* parent = nullptr);
  ~ParaViewMCPToolbar() override;

private:
  void constructor();
  void updateButtonAppearance();

  QToolButton* Button = nullptr;
  QLabel* StatusDot = nullptr;
  QWidget* Container = nullptr;
  ParaViewMCPPopup* Popup = nullptr;
};

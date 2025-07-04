import React from 'react';
import ReactDOM from 'react-dom';
import BotControl from './BotControl';
import BotStatus from './BotStatus';
import TradeLogs from './TradeLogs';
import BalanceStatus from './BalanceStatus';
import './App.css';

const App = () => {
  const [dummy, setDummy] = React.useState(0);
  const reload = () => setDummy(prev => prev + 1);

  return (
    <div className="app-container">
      <h1>Binance Trading Bot</h1>
      <BotControl onStatusChange={reload} />
      <BotStatus key={dummy} />
      <BalanceStatus />
      <TradeLogs key={dummy} />
    </div>
  );
};

ReactDOM.render(<App />, document.getElementById('root'));


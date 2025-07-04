// src/components/Gear.jsx
import React from 'react';
import { ReactComponent as GearIcon } from './gear.svg';

const Gear = ({ spinning }) => (
  <div className={'gear-icon' + (spinning ? ' spinning' : '')}>
    <GearIcon width={24} height={24} />
  </div>
);

export default Gear;

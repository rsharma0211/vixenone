import React, { useState } from 'react';
import { AskVixenFloatingButton } from './AskVixenFloatingButton';
import { AskVixenPanel } from './AskVixenPanel';

export const AskVixenWidget: React.FC = () => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  return (
    <>
      <AskVixenFloatingButton
        onClick={() => setIsOpen((prev) => !prev)}
        isOpen={isOpen}
      />
      <AskVixenPanel isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
};

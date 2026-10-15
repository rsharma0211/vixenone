import React from 'react';

interface AskVixenFloatingButtonProps {
  onClick: () => void;
  isOpen: boolean;
}

export const AskVixenFloatingButton: React.FC<AskVixenFloatingButtonProps> = ({
  onClick,
  isOpen,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Ask Vixen"
      title="Ask Vixen"
      aria-expanded={isOpen}
      className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg transition-all focus:outline-none focus:ring-2 focus:ring-navy focus:ring-offset-2 border border-border/50 print:hidden cursor-pointer"
    >
      <img
        src="/fox.png"
        alt=""
        className="h-8 w-8 object-contain pointer-events-none"
      />
    </button>
  );
};

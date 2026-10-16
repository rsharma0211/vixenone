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
      className="fixed bottom-6 right-6 z-40 flex h-[60px] w-[60px] items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg transition-all ring-2 ring-orange focus:outline-none focus:ring-2 focus:ring-orange focus:ring-offset-2 border border-border/50 print:hidden cursor-pointer"
    >
      <img
        src="/fox.png"
        alt="Ask Vixen"
        className="h-12 w-12 scale-110 object-contain pointer-events-none"
      />
    </button>
  );
};

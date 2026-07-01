import { twMerge } from "tailwind-merge"

interface CardProps {
  children: React.ReactNode
  className?: string
  onClick?: () => void
  hover?: boolean
  glass?: boolean
  liquid?: boolean
}

export function Card({ children, className, onClick, hover, glass, liquid }: CardProps) {
  const Comp = onClick ? "button" : "div"

  const shared = twMerge(
    "rounded-2xl text-left",
    hover && "hover-lift",
    onClick && "cursor-pointer active:scale-[0.98] transition-transform duration-200",
    className,
  )

  if (liquid) {
    return (
      <div className={twMerge("card-liquid rounded-2xl", shared)}>
        <Comp
          onClick={onClick}
          type={onClick ? "button" : undefined}
          className="w-full"
        >
          <div className="card-liquid-content p-5">{children}</div>
        </Comp>
      </div>
    )
  }

  return (
    <Comp
      onClick={onClick}
      type={onClick ? "button" : undefined}
      className={twMerge(
        shared,
        "p-5",
        glass
          ? "glass-strong shadow-apple-heavy"
          : "bg-white dark:bg-white/[0.06] shadow-apple dark:shadow-apple-dark",
      )}
    >
      {children}
    </Comp>
  )
}

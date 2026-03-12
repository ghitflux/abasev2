"use client";

import * as React from "react";

import { formatDateTimeValue, parseDateTimeValue } from "@/lib/date-value";
import { cn } from "@/lib/utils";
import DatePicker from "@/components/custom/date-picker";
import TimePicker from "@/components/custom/time-picker";

type DateTimePickerProps = {
  value?: string;
  onChange?: (value: string) => void;
  className?: string;
  disabled?: boolean;
};

export default function DateTimePicker({
  value,
  onChange,
  className,
  disabled,
}: DateTimePickerProps) {
  const [date, setDate] = React.useState<Date | undefined>(
    parseDateTimeValue(value),
  );
  const [time, setTime] = React.useState(
    value ? formatDateTimeValue(value).slice(11, 16) : "",
  );

  React.useEffect(() => {
    if (!value) {
      setDate(undefined);
      setTime("");
      return;
    }
    const parsed = parseDateTimeValue(value);
    if (!parsed || Number.isNaN(parsed.getTime())) return;
    setDate(parsed);
    setTime(
      `${String(parsed.getHours()).padStart(2, "0")}:${String(parsed.getMinutes()).padStart(2, "0")}`,
    );
  }, [value]);

  React.useEffect(() => {
    if (!date || !time) {
      onChange?.("");
      return;
    }

    if (!/^\d{2}:\d{2}$/.test(time)) {
      return;
    }

    const [hours, minutes] = time.split(":").map(Number);
    if (hours > 23 || minutes > 59) {
      return;
    }

    const nextDate = new Date(date);
    nextDate.setHours(hours, minutes, 0, 0);
    onChange?.(formatDateTimeValue(nextDate));
  }, [date, time, onChange]);

  return (
    <div className={cn("grid gap-3 sm:grid-cols-[1fr_140px]", className)}>
      <DatePicker value={date} onChange={setDate} disabled={disabled} />
      <TimePicker value={time} onChange={setTime} disabled={disabled} />
    </div>
  );
}

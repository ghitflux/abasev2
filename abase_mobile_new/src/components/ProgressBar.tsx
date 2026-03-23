// ProgressBar — cópia direta do legado
import React from 'react';
import { View, StyleSheet } from 'react-native';

type Props = {
  progress: number; // 0..100
  height?: number;
  trackColor?: string;
  fillColor?: string;
  borderRadius?: number;
};

export default function ProgressBar({
  progress,
  height = 8,
  trackColor = 'rgba(255,255,255,0.15)',
  fillColor = '#f472b6',
  borderRadius = 4,
}: Props) {
  const clamp = Math.min(100, Math.max(0, progress || 0));

  return (
    <View style={[styles.track, { height, backgroundColor: trackColor, borderRadius }]}>
      <View
        style={[
          styles.fill,
          { width: `${clamp}%`, backgroundColor: fillColor, borderRadius },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  track: { width: '100%', overflow: 'hidden' },
  fill: { height: '100%' },
});

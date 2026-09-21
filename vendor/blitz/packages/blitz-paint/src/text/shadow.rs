//! CSS text shadows reuse the foreground glyph and decoration geometry. The
//! computed list is inherited once; walking ancestors would duplicate shadows.
use super::{
    Color, LineDecoration, TextBrush, WinAscentCache, draw_glyph_run, flush_line_decorations,
};
use crate::layers::LayerManager;
use anyrender::{Filter, PaintScene, filters::FilterEffect};
use blitz_dom::util::ToColorColor;
use kurbo::{Affine, Rect, Vec2};
use parley::GlyphRun;
use std::sync::Arc;
use style::properties::ComputedValues;

#[derive(Clone, Debug, PartialEq)]
pub(super) struct ResolvedTextShadow {
    offset: Vec2,
    blur: f64,
    color: Color,
}

pub(super) fn resolve_shadows(style: &ComputedValues) -> Vec<ResolvedTextShadow> {
    let current_color = style.clone_color();
    style
        .get_inherited_text()
        .text_shadow
        .0
        .iter()
        .map(|shadow| ResolvedTextShadow {
            offset: Vec2::new(shadow.horizontal.px() as f64, shadow.vertical.px() as f64),
            blur: shadow.blur.px() as f64,
            color: shadow
                .color
                .resolve_to_absolute(&current_color)
                .as_color_color(),
        })
        .collect()
}

/// Adjacent runs sharing a computed shadow list use one mask per shadow. Font
/// fallback, bold spans and nested inherited spans therefore do not introduce
/// extra blur seams or reverse the shadow-list order at run boundaries.
pub(super) struct ShadowGroup<'a> {
    shadows: Vec<ResolvedTextShadow>,
    runs: Vec<GlyphRun<'a, TextBrush>>,
    bounds: Rect,
    x0: f64,
    x1: f64,
}

impl<'a> ShadowGroup<'a> {
    pub(super) fn push(
        groups: &mut Vec<Self>,
        run: GlyphRun<'a, TextBrush>,
        shadows: &[ResolvedTextShadow],
    ) {
        let x0 = run.offset() as f64;
        let x1 = x0 + run.advance() as f64;
        let metrics = run.run().metrics();
        let baseline = run.baseline() as f64;
        // Room for synthetic italics and font ink beyond typographic advances.
        let overhang = run.run().font_size() as f64 * 2.0;
        let bounds = Rect::new(
            x0,
            baseline - metrics.ascent as f64,
            x1,
            baseline + metrics.descent as f64,
        )
        .inflate(overhang, overhang);
        if let Some(last) = groups
            .last_mut()
            .filter(|group| group.shadows == shadows && (group.x1 - x0).abs() < 0.01)
        {
            last.bounds = last.bounds.union(bounds);
            last.x0 = last.x0.min(x0);
            last.x1 = last.x1.max(x1);
            last.runs.push(run);
        } else {
            groups.push(Self {
                shadows: shadows.to_vec(),
                runs: vec![run],
                bounds,
                x0,
                x1,
            });
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub(super) fn paint(
        &self,
        scene: &mut impl PaintScene,
        transform: Affine,
        scale: f64,
        decorations: &[LineDecoration],
        ascent_cache: &mut WinAscentCache,
        layers: &LayerManager,
    ) {
        if self.shadows.is_empty() {
            return;
        }
        // Decorations retain the decorating ancestor's metrics, while their
        // shadow is determined by the inline descendant under that segment.
        let decorations: Vec<_> = decorations
            .iter()
            .filter_map(|deco| {
                let mut deco = deco.clone();
                deco.min_x = deco.min_x.max(self.x0);
                deco.max_x = deco.max_x.min(self.x1);
                (deco.min_x < deco.max_x).then_some(deco)
            })
            .collect();
        let mut bounds = self.bounds;
        for deco in &decorations {
            if let Some(geom) = deco.own.as_ref().or(deco.first.as_ref()) {
                let offset = deco
                    .deco
                    .underline_offset
                    .as_ref()
                    .map(|offset| {
                        offset
                            .resolve(style::values::computed::Length::new(
                                geom.css_font_size as f32,
                            ))
                            .px()
                            .abs() as f64
                            * scale
                    })
                    .unwrap_or(0.0);
                bounds = bounds.inflate(0.0, offset);
            }
        }
        // CSS lists are front-to-back. Paint the last entry first, then text.
        for shadow in self.shadows.iter().rev() {
            if shadow.color.components[3] == 0.0 {
                continue;
            }
            let transform = transform * Affine::translate(shadow.offset * scale);
            // CSS shadow blur radius is twice the Gaussian standard deviation.
            let sigma = shadow.blur * scale * 0.5;
            let filter =
                (sigma > 0.0).then(|| Arc::new(Filter::single(FilterEffect::blur(sigma as f32))));
            layers.maybe_with_layer(
                scene,
                filter.is_some(),
                1.0,
                transform,
                &bounds.inflate(sigma * 3.0, sigma * 3.0),
                filter,
                None,
                |scene| {
                    for run in &self.runs {
                        draw_glyph_run(scene, run, transform, scale, shadow.color);
                    }
                    flush_line_decorations(
                        scene,
                        transform,
                        scale,
                        &decorations,
                        ascent_cache,
                        Some(shadow.color),
                    );
                },
            );
        }
    }
}

/// Text shadows are ink overflow, not scrollable overflow. Until the engine has
/// cached subtree ink bounds, conservatively retain branches with shadows when
/// culling offscreen boxes. Ancestor/scrollport clip layers still apply. Walking
/// both trees also covers anonymous table and inline formatting boxes.
pub(crate) fn shadowed_subtrees(
    doc: &blitz_dom::BaseDocument,
) -> std::collections::HashSet<blitz_dom::NodeId> {
    let mut retained = std::collections::HashSet::new();
    let mut pending = Vec::new();
    for (_, node) in doc.tree().iter() {
        if !node
            .primary_styles()
            .is_some_and(|style| !style.get_inherited_text().text_shadow.0.is_empty())
        {
            continue;
        }
        pending.push(node.id);
        while let Some(id) = pending.pop() {
            if !retained.insert(id) {
                continue;
            }
            if let Some(node) = doc.get_node(id) {
                pending.extend(node.parent);
                pending.extend(node.layout_parent.get());
            }
        }
    }
    retained
}

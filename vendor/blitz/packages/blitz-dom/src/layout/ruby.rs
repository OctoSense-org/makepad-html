//! Horizontal HTML ruby base/annotation pairs. Anonymous base boxes retain the
//! source DOM and are owned by the normal reconstruction/deallocation path.
use super::construct::LayoutChildren;
use crate::{BaseDocument, Node};
use blitz_traits::node_id::NodeId;
use markup5ever::local_name;
use style::values::computed::Display;
use taffy::{
    AvailableSpace, Baselines, LayoutInput, LayoutOutput, LayoutPartialTree, Point, RunMode, Size,
};

pub(super) fn is_ruby(node: &Node) -> bool {
    node.element_data()
        .is_some_and(|el| el.name.local == local_name!("ruby"))
        && node.display_style() == Some(Display::InlineBlock)
}
fn is_annotation(node: &Node) -> bool {
    node.element_data()
        .is_some_and(|el| el.name.local == local_name!("rt"))
}
pub(super) fn construct(doc: &mut BaseDocument, root: NodeId, out: &mut LayoutChildren) {
    let children = doc.nodes[root].children.clone();
    let mut base = None;
    for child in children {
        let node = &doc.nodes[child];
        if node.display_style() == Some(Display::None)
            || node.data.kind() == crate::node::NodeKind::Comment
        {
            continue;
        }
        if is_annotation(node) {
            out.children.push(child);
            doc.nodes[child].layout_parent.set(Some(root));
            base = None;
        } else {
            let wrapper = *base.get_or_insert_with(|| {
                let mut generated = LayoutChildren::default();
                generated.create_anonymous_block(root, doc);
                let id = generated.anonymous_block_id.unwrap();
                out.children.push(id);
                out.anonymous_blocks.push(id);
                id
            });
            doc.nodes[wrapper].children.push(child);
        }
    }
}

pub(super) fn compute(doc: &mut BaseDocument, root: NodeId, inputs: LayoutInput) -> LayoutOutput {
    let children = doc.nodes[root]
        .layout_children
        .borrow()
        .as_ref()
        .cloned()
        .unwrap_or_default();
    let child_inputs = LayoutInput {
        known_dimensions: Size::NONE,
        available_space: Size {
            width: AvailableSpace::MaxContent,
            height: AvailableSpace::MaxContent,
        },
        vertical_margins_are_collapsible: taffy::Line::FALSE,
        ..inputs
    };
    let mut pairs = Vec::new();
    let mut index = 0;
    let mut above = 0.0_f32;
    let mut below = 0.0_f32;
    let mut width = 0.0;
    while index < children.len() {
        let base = children[index];
        let base_layout =
            doc.compute_child_layout(taffy::NodeId::from(base.as_u64()), child_inputs);
        let annotation = children
            .get(index + 1)
            .copied()
            .filter(|id| is_annotation(&doc.nodes[*id]));
        let annotation_layout = annotation
            .map(|id| doc.compute_child_layout(taffy::NodeId::from(id.as_u64()), child_inputs));
        let annotation_size = annotation_layout
            .as_ref()
            .map(|l| l.size)
            .unwrap_or(Size::ZERO);
        let baseline = base_layout
            .baselines
            .first
            .unwrap_or(base_layout.size.height);
        let pair_width = base_layout.size.width.max(annotation_size.width);
        above = above.max(annotation_size.height + baseline);
        below = below.max(base_layout.size.height - baseline);
        pairs.push((
            base,
            base_layout,
            annotation,
            annotation_layout,
            width,
            pair_width,
            baseline,
        ));
        width += pair_width;
        index += if annotation.is_some() { 2 } else { 1 };
    }
    if inputs.run_mode == RunMode::PerformLayout {
        for (base, base_layout, annotation, annotation_layout, x, pair_width, baseline) in pairs {
            let layout = doc.nodes[base].unrounded_layout_mut();
            layout.location = Point {
                x: x + (pair_width - base_layout.size.width) / 2.0,
                y: above - baseline,
            };
            layout.size = base_layout.size;
            layout.scrollable_overflow_rect = base_layout.scrollable_overflow_rect;
            if let Some((id, output)) = annotation.zip(annotation_layout) {
                let layout = doc.nodes[id].unrounded_layout_mut();
                layout.location = Point {
                    x: x + (pair_width - output.size.width) / 2.0,
                    y: above - baseline - output.size.height,
                };
                layout.size = output.size;
                layout.scrollable_overflow_rect = output.scrollable_overflow_rect;
            }
        }
    }
    let size = Size {
        width,
        height: above + below,
    };
    LayoutOutput::from_sizes_and_baselines(
        size,
        taffy::Rect {
            left: 0.0,
            top: 0.0,
            right: size.width,
            bottom: size.height,
        },
        Baselines {
            first: Some(above),
            last: Some(above),
        },
    )
}

export const modelCatalog = [
  {
    id: "lss",
    modelDir: "LSS",
    modelFile: "LSS.model3.json",
    displayName: "LSS",
    view: { scale: 1, x: 0, y: 0 }
  },
  {
    id: "13",
    modelDir: "13",
    modelFile: "13.model3.json",
    displayName: "13",
    view: { scale: 1, x: 0, y: 0 }
  },
  {
    id: "hiyori_pro_t11",
    modelDir: "hiyori_pro_t11",
    modelFile: "hiyori_pro_t11.model3.json",
    displayName: "hiyori_pro_t11",
    view: { scale: 1, x: 0, y: 0 }
  }
];

export function findModel(modelId) {
  return modelCatalog.find((model) => model.id === modelId) ?? modelCatalog[0];
}

export function modelAssetUrl(model, fileName) {
  return `/l2d/${model.modelDir}/${fileName}`;
}

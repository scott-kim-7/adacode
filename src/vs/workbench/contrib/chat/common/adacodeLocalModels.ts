/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import { ILanguageModelChatMetadataAndIdentifier } from './languageModels.js';

/** BYOK vendors used for adacode Step 1 local MLX (chatLanguageModels.json). */
export const ADA_LOCAL_BYOK_VENDORS: readonly string[] = ['customendpoint'];

export function isAdacodeLocalByokModel(model: ILanguageModelChatMetadataAndIdentifier): boolean {
	return ADA_LOCAL_BYOK_VENDORS.includes(model.metadata.vendor)
		&& !model.metadata.targetChatSessionType
		&& model.metadata.isUserSelectable !== false;
}

export function getAdacodeLocalByokModels(
	models: readonly ILanguageModelChatMetadataAndIdentifier[],
): ILanguageModelChatMetadataAndIdentifier[] {
	return models.filter(isAdacodeLocalByokModel);
}
